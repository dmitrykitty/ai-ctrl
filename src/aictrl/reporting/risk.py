"""Explainable, windowed risk from safe event identifiers only."""

from aictrl.contracts import SecurityEvent, Severity
from aictrl.policy.models import RiskSettings

LEVELS = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3}


class RiskEngine:
    def __init__(self, settings: RiskSettings) -> None:
        self.settings = settings

    def contribution(self, event: SecurityEvent) -> tuple[str, int] | None:
        if event.action != 'BLOCK':
            return None
        identifiers = (event.reason_code, *event.rule_ids)
        matches = [(value, len(rule), rule) for rule, value in self.settings.weights.items()
                   if value and any(item == rule or item.startswith(rule + '.') for item in identifiers)]
        if not matches:
            return None
        # At most one contribution/event. Never count its correlated AUDIT or
        # multiple aliases of one reason as separate incidents.
        value, _, rule = max(matches)
        return rule, value

    def severity(self, score: int | float) -> Severity:
        thresholds = self.settings.thresholds
        for level, minimum in (('CRITICAL', thresholds.critical), ('HIGH', thresholds.high), ('MEDIUM', thresholds.medium)):
            if score >= minimum:
                return Severity(level)
        return Severity.LOW
