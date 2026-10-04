"""Shared safe and synchronous durable event construction."""

import asyncio
from datetime import datetime, timezone

from aictrl.contracts import ControlRequest, DecisionAction, SecurityEvent, UsageMetric
from aictrl.gateway.session import GatewaySession
from aictrl.reporting.sink import EventSink
from aictrl.reporting.service import ReportingStore
from aictrl.policy.models import RiskSettings, ResponseSettings


class EventRecorder:
    def __init__(self, session: GatewaySession, policy_version: str, sink: EventSink, *,
                 reporting: ReportingStore | None = None, risk: RiskSettings | None = None,
                 response: ResponseSettings | None = None) -> None:
        self.session, self.policy_version, self.sink = session, policy_version, sink
        self.reporting, self.risk, self.response = reporting, risk or RiskSettings(), response or ResponseSettings()

    def event(self, request: ControlRequest, action: DecisionAction, reason: str,
              identifiers: tuple[str, ...] = (), *, usage: UsageMetric | None = None) -> SecurityEvent:
        return SecurityEvent(session_id=self.session.session_id, request_id=request.request_id,
                             agent_id=self.session.agent_id, adapter=self.session.adapter,
                             channel=request.channel, direction=request.direction, protocol=request.protocol,
                             inspection_level=request.inspection_level, action=action, reason_code=reason,
                             policy_version=self.policy_version,
                             usage=usage,
                             rule_ids=('operation.' + request.operation_id, *identifiers), occurred_at=datetime.now(timezone.utc))

    async def record(self, request: ControlRequest, action: DecisionAction, reason: str,
                     identifiers: tuple[str, ...] = (), *, usage: UsageMetric | None = None) -> None:
        event = self.event(request, action, reason, identifiers, usage=usage)
        await asyncio.to_thread(self.sink.append, event)
        if self.reporting is not None:
            await asyncio.to_thread(self.reporting.observe_event, event, self.risk, self.response)
