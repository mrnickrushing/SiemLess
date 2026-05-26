"""
Search router: full-text and structured search across security events.

Query syntax (with proper operator precedence):
  - Free text:          `failed ssh`
  - Field filters:      `severity:high`, `source_ip:10.0.0.1`
  - Quoted values:      `hostname:"web-server-01"`
  - AND (higher prec):  `severity:high AND user:admin`
  - OR  (lower prec):   `severity:critical OR severity:high`
  - NOT:                `NOT severity:low`
  - Grouping:           `severity:high AND (source_ip:10.0.0.1 OR source_ip:192.168.1.1)`
  - Implicit AND:       `failed ssh` → `failed AND ssh`

Security hardening:
  - Per-user rate limiting (60 req/min)
  - Max query length (500 chars) and token count (20)
  - ILIKE wildcard escaping (% and _ in user input are literals, not wildcards)
  - Query execution timeout (5 s)
  - Sensitive field redaction in raw_log output
  - Audit log of every search with username
"""
import asyncio
import logging
import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models.event import SecurityEvent

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input validation limits
# ---------------------------------------------------------------------------
_MAX_QUERY_LEN = 500
_MAX_TOKENS = 20
_QUERY_TIMEOUT = 5.0  # seconds

# ---------------------------------------------------------------------------
# Rate limiting (per authenticated user)
# ---------------------------------------------------------------------------
_RATE_WINDOW = 60   # seconds
_RATE_LIMIT = 60    # requests per window
_rate_attempts: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(username: str) -> None:
    now = time.monotonic()
    cutoff = now - _RATE_WINDOW
    attempts = [t for t in _rate_attempts[username] if t >= cutoff]
    if len(attempts) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Search rate limit exceeded. Try again later.",
            headers={"Retry-After": str(_RATE_WINDOW)},
        )
    attempts.append(now)
    _rate_attempts[username] = attempts


# ---------------------------------------------------------------------------
# Sensitive field redaction
# Strips credentials / tokens from raw_log before returning to clients.
# ---------------------------------------------------------------------------
_REDACT_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r'(?i)(password\s*[=:]\s*)\S+'),          r'\1[REDACTED]'),
    (re.compile(r'(?i)(passwd\s*[=:]\s*)\S+'),            r'\1[REDACTED]'),
    (re.compile(r'(?i)(secret\s*[=:]\s*)\S+'),            r'\1[REDACTED]'),
    (re.compile(r'(?i)(token\s*[=:]\s*)\S+'),             r'\1[REDACTED]'),
    (re.compile(r'(?i)(api[_-]?key\s*[=:]\s*)\S+'),       r'\1[REDACTED]'),
    (re.compile(r'(?i)(private[_-]?key\s*[=:]\s*)\S+'),   r'\1[REDACTED]'),
    (re.compile(r'(?i)(authorization:\s*(?:bearer|basic)\s+)\S+'), r'\1[REDACTED]'),
]


def _redact(text: str | None) -> str | None:
    if not text:
        return text
    for pattern, replacement in _REDACT_RULES:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# ILIKE wildcard escaping
# Prevents user-supplied % and _ from acting as ILIKE wildcards.
# ---------------------------------------------------------------------------
def _escape_ilike(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------------------
# Known filterable fields (allowlist prevents arbitrary column access)
# ---------------------------------------------------------------------------
FIELD_MAP = {
    "severity":       SecurityEvent.severity,
    "category":       SecurityEvent.category,
    "log_type":       SecurityEvent.log_type,
    "log_source":     SecurityEvent.log_source,
    "source_ip":      SecurityEvent.source_ip,
    "destination_ip": SecurityEvent.destination_ip,
    "hostname":       SecurityEvent.hostname,
    "user":           SecurityEvent.user,
    "process":        SecurityEvent.process,
    "action":         SecurityEvent.action,
    "country":        SecurityEvent.country,
}

_FIELD_TERM_RE = re.compile(r'^(\w+):(.+)$')


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------
class _T:
    AND    = "AND"
    OR     = "OR"
    NOT    = "NOT"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    TERM   = "TERM"
    EOF    = "EOF"


def _tokenize(q: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    i = 0
    while i < len(q):
        ch = q[i]
        if ch.isspace():
            i += 1
            continue
        if ch == '(':
            tokens.append((_T.LPAREN, '('))
            i += 1
            continue
        if ch == ')':
            tokens.append((_T.RPAREN, ')'))
            i += 1
            continue
        if ch == '"':
            # Quoted term: consume until closing quote
            j = i + 1
            while j < len(q) and q[j] != '"':
                j += 1
            tokens.append((_T.TERM, q[i + 1:j]))
            i = j + 1
            continue
        # Unquoted word: up to whitespace or parens
        j = i
        while j < len(q) and not q[j].isspace() and q[j] not in '()"':
            j += 1
        word = q[i:j]
        i = j
        upper = word.upper()
        if upper == "AND":
            tokens.append((_T.AND, word))
        elif upper == "OR":
            tokens.append((_T.OR, word))
        elif upper == "NOT":
            tokens.append((_T.NOT, word))
        else:
            tokens.append((_T.TERM, word))

    tokens.append((_T.EOF, ""))
    return tokens


# ---------------------------------------------------------------------------
# Recursive-descent parser  →  AST
#
# Grammar (standard boolean precedence: NOT > AND > OR):
#   expr     := and_expr  (OR  and_expr)*
#   and_expr := not_expr  (AND? not_expr)*   ← implicit AND for adjacent atoms
#   not_expr := NOT? atom
#   atom     := LPAREN expr RPAREN | TERM
#
# AST nodes: ("AND", l, r) | ("OR", l, r) | ("NOT", child) | ("TERM", value)
# ---------------------------------------------------------------------------
class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> str:
        return self._tokens[self._pos][0]

    def _value(self) -> str:
        return self._tokens[self._pos][1]

    def _consume(self, expected: str | None = None) -> str:
        tok_type, tok_val = self._tokens[self._pos]
        if expected and tok_type != expected:
            raise ValueError(f"Parse error: expected {expected}, got {tok_type!r} ({tok_val!r})")
        self._pos += 1
        return tok_val

    def parse(self) -> tuple:
        node = self._expr()
        if self._peek() != _T.EOF:
            raise ValueError(f"Unexpected token: {self._value()!r}")
        return node

    def _expr(self) -> tuple:
        left = self._and_expr()
        while self._peek() == _T.OR:
            self._consume(_T.OR)
            right = self._and_expr()
            left = ("OR", left, right)
        return left

    def _and_expr(self) -> tuple:
        left = self._not_expr()
        # Continue while next token can start another atom (explicit or implicit AND)
        while self._peek() in (_T.AND, _T.TERM, _T.LPAREN, _T.NOT):
            if self._peek() == _T.AND:
                self._consume(_T.AND)
            right = self._not_expr()
            left = ("AND", left, right)
        return left

    def _not_expr(self) -> tuple:
        if self._peek() == _T.NOT:
            self._consume(_T.NOT)
            return ("NOT", self._atom())
        return self._atom()

    def _atom(self) -> tuple:
        if self._peek() == _T.LPAREN:
            self._consume(_T.LPAREN)
            node = self._expr()
            self._consume(_T.RPAREN)
            return node
        return ("TERM", self._consume(_T.TERM))


# ---------------------------------------------------------------------------
# AST → SQLAlchemy clause
# ---------------------------------------------------------------------------
def _ast_to_clause(node: tuple, highlight_terms: list[str]) -> Any:
    kind = node[0]

    if kind == "AND":
        return and_(
            _ast_to_clause(node[1], highlight_terms),
            _ast_to_clause(node[2], highlight_terms),
        )
    if kind == "OR":
        return or_(
            _ast_to_clause(node[1], highlight_terms),
            _ast_to_clause(node[2], highlight_terms),
        )
    if kind == "NOT":
        return not_(_ast_to_clause(node[1], highlight_terms))

    # TERM: check for field:value, else full-text
    value: str = node[1]
    m = _FIELD_TERM_RE.match(value)
    if m:
        field = m.group(1).lower()
        val = m.group(2).strip('"')
        if field in FIELD_MAP:
            escaped = _escape_ilike(val)
            highlight_terms.append(val)
            return FIELD_MAP[field].ilike(f"%{escaped}%", escape="\\")
        # Unknown field name → fall through to full-text search

    escaped = _escape_ilike(value)
    highlight_terms.append(value)
    return or_(
        SecurityEvent.message.ilike(f"%{escaped}%", escape="\\"),
        SecurityEvent.raw_log.ilike(f"%{escaped}%", escape="\\"),
        SecurityEvent.hostname.ilike(f"%{escaped}%", escape="\\"),
        SecurityEvent.source_ip.ilike(f"%{escaped}%", escape="\\"),
        SecurityEvent.user.ilike(f"%{escaped}%", escape="\\"),
    )


def _build_search_clause(q: str) -> tuple[Any, list[str]]:
    """Parse query string → (sqlalchemy clause, highlight terms). Raises ValueError on bad input."""
    if len(q) > _MAX_QUERY_LEN:
        raise ValueError(f"Query too long (max {_MAX_QUERY_LEN} characters)")

    tokens = _tokenize(q)
    term_count = sum(1 for t in tokens if t[0] == _T.TERM)
    if term_count > _MAX_TOKENS:
        raise ValueError(f"Too many search terms (max {_MAX_TOKENS})")
    if term_count == 0:
        raise ValueError("No search terms found in query")

    ast = _Parser(tokens).parse()
    highlight_terms: list[str] = []
    clause = _ast_to_clause(ast, highlight_terms)
    return clause, highlight_terms


# ---------------------------------------------------------------------------
# Highlight helper
# ---------------------------------------------------------------------------
def _build_highlight(text_content: str | None, terms: list[str], max_len: int = 200) -> str:
    if not text_content or not terms:
        return (text_content or "")[:max_len]
    text_lower = text_content.lower()
    for term in terms:
        idx = text_lower.find(term.lower())
        if idx != -1:
            start = max(0, idx - 60)
            end = min(len(text_content), idx + len(term) + 60)
            snippet = text_content[start:end]
            highlight = snippet.replace(
                text_content[idx:idx + len(term)],
                f"**{text_content[idx:idx + len(term)]}**",
                1,
            )
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(text_content) else ""
            return f"{prefix}{highlight}{suffix}"
    return text_content[:max_len]


# ---------------------------------------------------------------------------
# Async query runner (extracted so asyncio.wait_for can timeout both queries)
# ---------------------------------------------------------------------------
async def _run_queries(db: AsyncSession, count_query: Any, data_query: Any) -> tuple:
    total_result = await db.execute(count_query)
    result = await db.execute(data_query)
    return total_result, result


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@router.get("", response_model=dict, summary="Full-text and structured search across events")
async def search_events(
    request: Request,
    q: str = Query(
        ...,
        min_length=1,
        max_length=_MAX_QUERY_LEN,
        description=(
            "Search query. Supports field:value, AND/OR/NOT with correct precedence, "
            "parentheses grouping, and implicit AND for adjacent terms."
        ),
    ),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=settings.MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_user),
) -> dict:
    """
    Search security events with a full boolean query language.

    Examples:
    - `failed ssh` — implicit AND, full-text
    - `severity:high AND source_ip:10.0.0.1`
    - `severity:critical OR severity:high`
    - `severity:high AND (source_ip:10.0.0.1 OR source_ip:192.168.1.1)`
    - `NOT severity:low AND user:admin`
    """
    _check_rate_limit(username)

    try:
        search_clause, highlight_terms = _build_search_clause(q.strip())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    logger.info("SEARCH user=%s query=%r page=%d page_size=%d", username, q, page, page_size)

    base_query = select(SecurityEvent)
    count_base = select(func.count()).select_from(SecurityEvent)

    conditions: list[Any] = []
    if start_time:
        conditions.append(SecurityEvent.timestamp >= start_time)
    if end_time:
        conditions.append(SecurityEvent.timestamp <= end_time)
    conditions.append(search_clause)

    base_query = base_query.where(*conditions)
    count_base = count_base.where(*conditions)

    offset = (page - 1) * page_size
    base_query = base_query.order_by(SecurityEvent.timestamp.desc()).offset(offset).limit(page_size)

    try:
        total_result, result = await asyncio.wait_for(
            _run_queries(db, count_base, base_query),
            timeout=_QUERY_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Search query timed out. Narrow your search criteria and try again.",
        )

    total = total_result.scalar() or 0
    events = list(result.scalars().all())

    items = []
    for event in events:
        raw_log_safe = _redact(event.raw_log)
        items.append({
            "id": str(event.id),
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "received_at": event.received_at.isoformat() if event.received_at else None,
            "source_ip": event.source_ip,
            "destination_ip": event.destination_ip,
            "source_port": event.source_port,
            "destination_port": event.destination_port,
            "hostname": event.hostname,
            "log_source": event.log_source,
            "log_type": event.log_type,
            "severity": event.severity,
            "category": event.category,
            "message": event.message,
            "raw_log": raw_log_safe,
            "parsed_fields": event.parsed_fields,
            "tags": event.tags,
            "country": event.country,
            "user": event.user,
            "process": event.process,
            "action": event.action,
            "_highlight": {
                "message": _build_highlight(event.message, highlight_terms),
                "raw_log": _build_highlight(raw_log_safe, highlight_terms),
            },
        })

    return {
        "query": q,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }
