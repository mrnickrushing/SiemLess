"""
Async UDP/TCP syslog server (RFC 3164 / RFC 5424).
Runs as a background asyncio task, parses incoming datagrams,
and stores them as SecurityEvents.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from sqlalchemy import select

from app.models.event import SecurityEvent
from app.models.rule import CorrelationRule
from app.services.log_parser import LogParser

logger = logging.getLogger(__name__)

_log_parser = LogParser()


class SyslogUDPProtocol(asyncio.DatagramProtocol):
    """asyncio UDP protocol for syslog ingestion."""

    def __init__(self, message_queue: asyncio.Queue) -> None:
        self._queue = message_queue
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:  # type: ignore[override]
        self.transport = transport
        logger.info("Syslog UDP server ready")

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            raw = data.decode("utf-8", errors="replace").strip()
            if raw:
                self._queue.put_nowait((raw, addr[0]))
        except Exception as exc:
            logger.debug("Error decoding syslog datagram from %s: %s", addr, exc)

    def error_received(self, exc: Exception) -> None:
        logger.warning("Syslog UDP error: %s", exc)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        logger.info("Syslog UDP connection closed: %s", exc)


async def _store_event(raw_log: str, source_ip: str) -> None:
    """Parse and store a single syslog message."""
    try:
        parsed = _log_parser.parse(raw_log, log_source="syslog")
        if not parsed.get("source_ip"):
            parsed["source_ip"] = source_ip

        event_schema = _log_parser.normalize(parsed)

        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            event = SecurityEvent(
                id=uuid.uuid4(),
                timestamp=event_schema.timestamp or now,
                received_at=now,
                source_ip=event_schema.source_ip,
                destination_ip=event_schema.destination_ip,
                source_port=event_schema.source_port,
                destination_port=event_schema.destination_port,
                hostname=event_schema.hostname,
                log_source="syslog",
                log_type=event_schema.log_type,
                severity=event_schema.severity,
                category=event_schema.category,
                message=event_schema.message,
                raw_log=raw_log,
                parsed_fields=event_schema.parsed_fields,
                tags=event_schema.tags,
                user=event_schema.user,
                process=event_schema.process,
                action=event_schema.action,
            )
            db.add(event)
            await db.commit()
            logger.debug("Stored syslog event %s from %s", event.id, source_ip)

            try:
                from app.services.correlation import correlation_engine
                from app.services.alerting import alert_service
                alerts = await correlation_engine.evaluate_event(db, event)
                for alert in alerts:
                    rule_result = await db.execute(
                        select(CorrelationRule).where(CorrelationRule.id == alert.rule_id)
                    )
                    rule = rule_result.scalar_one_or_none()
                    await alert_service.send_alert(alert, rule)
                # Commit alerts created by correlation engine — evaluate_event uses
                # db.flush() internally so the alert IDs are assigned, but the session
                # is not committed until here. Without this, syslog-triggered alerts
                # are flushed but never persisted to the DB.
                if alerts:
                    await db.commit()
            except Exception as exc:
                logger.warning("Correlation/alerting error for syslog event: %s", exc)

    except Exception as exc:
        logger.error("Failed to store syslog event from %s: %s", source_ip, exc)


async def _process_queue(queue: asyncio.Queue) -> None:
    """Consumer task: reads from queue and stores events."""
    logger.info("Syslog message processor started")
    while True:
        try:
            raw_log, source_ip = await queue.get()
            await _store_event(raw_log, source_ip)
            queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Error in syslog processor: %s", exc)


class SyslogServer:
    """Manages async UDP and TCP syslog listeners."""

    def __init__(self) -> None:
        self._udp_transport: Optional[asyncio.DatagramTransport] = None
        self._tcp_server: Optional[asyncio.AbstractServer] = None
        self._processor_task: Optional[asyncio.Task] = None
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._running = False

    async def start(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        host = host or settings.SYSLOG_HOST
        port = port or settings.SYSLOG_PORT

        # FIX: use get_running_loop() — get_event_loop() is deprecated in Python 3.10+
        loop = asyncio.get_running_loop()

        self._processor_task = asyncio.create_task(_process_queue(self._queue))

        # Start UDP listener
        # NOTE: Port 514 requires root/CAP_NET_BIND_SERVICE on Linux.
        # If binding fails, syslog ingestion is silently disabled for that
        # protocol. The /health endpoint reflects syslog.is_running status.
        try:
            transport, _ = await loop.create_datagram_endpoint(
                lambda: SyslogUDPProtocol(self._queue),
                local_addr=(host, port),
            )
            self._udp_transport = transport  # type: ignore[assignment]
            logger.info("Syslog UDP server listening on %s:%d", host, port)
        except OSError as exc:
            logger.warning(
                "Could not bind syslog UDP port %d: %s. "
                "Check that the process has CAP_NET_BIND_SERVICE or run on a port > 1024.",
                port, exc
            )

        # Start TCP listener
        try:
            self._tcp_server = await asyncio.start_server(
                lambda r, w: self._handle_tcp_client(r, w),
                host=host,
                port=port,
            )
            logger.info("Syslog TCP server listening on %s:%d", host, port)
        except OSError as exc:
            logger.warning("Could not bind syslog TCP port %d: %s", port, exc)

        self._running = True

    async def _handle_tcp_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        source_ip = peer[0] if peer else "unknown"
        try:
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=60.0)
                if not line:
                    break
                raw = line.decode("utf-8", errors="replace").strip()
                if raw:
                    try:
                        self._queue.put_nowait((raw, source_ip))
                    except asyncio.QueueFull:
                        logger.warning("Syslog queue full, dropping TCP message")
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionResetError):
            pass
        except Exception as exc:
            logger.debug("TCP client %s error: %s", source_ip, exc)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def stop(self) -> None:
        self._running = False

        if self._udp_transport:
            self._udp_transport.close()
            self._udp_transport = None

        if self._tcp_server:
            self._tcp_server.close()
            await self._tcp_server.wait_closed()
            self._tcp_server = None

        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None

        logger.info("Syslog server stopped")

    @property
    def is_running(self) -> bool:
        return self._running


# Module-level singleton
syslog_server = SyslogServer()
