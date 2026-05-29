"""
Risk aggregation service: computes numeric risk scores (0–100) for events
and alerts based on severity, threat-intel matches, watchlist hits, and
alert hit_count.
"""
import math
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.event import SecurityEvent
    from app.models.alert import Alert

logger = logging.getLogger(__name__)

SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 100.0,
    "high": 75.0,
    "medium": 50.0,
    "low": 25.0,
    "info": 10.0,
}


class RiskAggregationService:
    """Computes risk scores for SecurityEvent and Alert objects."""

    def compute_event_risk_score(self, event: "SecurityEvent") -> float:
        """
        Compute a normalized risk score (0–100) for a SecurityEvent.
        
        The score is derived from the event's severity and is increased when the event contains
        threat-intel matches or watchlist-related tags. The final value is clamped to the range 0–100.
        
        Parameters:
            event (SecurityEvent): The security event to evaluate.
        
        Returns:
            risk_score (float): Risk score between 0 and 100.
        """
        base = SEVERITY_WEIGHTS.get((event.severity or "info").lower(), 10.0)

        # Boost if there is a threat-intel match in parsed_fields
        pf = event.parsed_fields or {}
        if pf.get("threat_matches") or pf.get("threat_intel_match"):
            base = min(100.0, base * 1.3)

        # Boost if watchlist match (tag-based)
        tags = event.tags or []
        if any(t == "watchlist-match" or t.startswith("watchlist:") for t in tags):
            base = min(100.0, base * 1.2)

        return min(100.0, float(base))

    def compute_alert_risk_score(self, alert: "Alert") -> float:
        """
        Compute a normalized 0–100 risk score for an Alert using its severity and hit count.
        
        Scales a severity-based base weight by a multiplier of 1 + log10(hit_count) (with a minimum hit_count of 1) and caps the result at 100.
        
        Parameters:
            alert (Alert): Alert whose `severity` (defaults to "medium" if missing) and `hit_count` (defaults to 1 if missing or falsy) are used to compute the score.
        
        Returns:
            float: Risk score between 0 and 100 inclusive.
        """
        base = SEVERITY_WEIGHTS.get((alert.severity or "medium").lower(), 50.0)
        hit_count = max(1, alert.hit_count or 1)
        hit_multiplier = 1.0 + math.log10(hit_count)
        return min(100.0, base * hit_multiplier)


# Module-level singleton
risk_aggregation_service = RiskAggregationService()
