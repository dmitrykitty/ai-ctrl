"""Independent authorization on every operation, before backend execution."""

from datetime import datetime, timezone
from typing import Any

import jsonschema

from aictrl.contracts import ControlRequest, DecisionAction, PolicyContext
from aictrl.gateway.audit import EventRecorder
from aictrl.gateway.inspection import strings
from aictrl.gateway.session import GatewaySession
from aictrl.guards.engine import GuardEngine
from aictrl.guards.models import InspectionSegment, Source, apply_replacements
from aictrl.mcp.backend import MCPBackend
from aictrl.policy.engine import PolicyEngine
from aictrl.reporting.sink import EventSink, StoreFailure


class MCPBlocked(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__('AICTRL MCP operation blocked: ' + reason)


class MCPControlService:
    def __init__(self, session: GatewaySession, policy: PolicyEngine, guards: GuardEngine,
                 sink: EventSink, backend: MCPBackend) -> None:
        self.session, self.policy, self.guards, self.backend = session, policy, guards, backend
        self.audit = EventRecorder(session, policy.policy.policy_version, sink)
        self.context = PolicyContext(session_id=session.session_id, agent_id=session.agent_id,
                                     user_id=session.user_id, profile_id=session.profile_id,
                                     policy_version=policy.policy.policy_version)

    def request(self, operation: str) -> ControlRequest:
        return ControlRequest(session_id=self.session.session_id, channel='MCP', direction='OUTBOUND',
                              protocol=None, inspection_level='STRUCTURED', target_id='demo-mcp',
                              operation_id=operation, created_at=datetime.now(timezone.utc))

    def allowed(self, operation: str) -> bool:
        return self.policy.decide(self.context, self.request(operation)).action == DecisionAction.ALLOW

    async def block(self, control: ControlRequest, reason: str, identifiers: tuple[str, ...] = ()) -> None:
        await self.audit.record(control, DecisionAction.BLOCK, reason, identifiers)
        raise MCPBlocked(reason)

    async def authorize(self, control: ControlRequest) -> None:
        try:
            allowed = self.policy.decide(self.context, control).action == DecisionAction.ALLOW
        except Exception:
            await self.block(control, 'mcp.policy_error')
            return
        if not allowed:
            await self.block(control, 'mcp.policy.blocked')

    async def list_tools(self):
        control = self.request('tools.list')
        await self.authorize(control)
        visible = tuple(tool for tool in self.backend.list_tools() if self.allowed(tool.operation))
        await self.audit.record(control, DecisionAction.ALLOW, 'mcp.policy.allowed')
        await self.audit.record(control, DecisionAction.AUDIT, 'mcp.discovery_completed')
        return visible

    async def list_resources(self):
        control = self.request('resources.list')
        await self.authorize(control)
        visible = tuple(resource for resource in self.backend.list_resources() if self.allowed(resource.operation))
        await self.audit.record(control, DecisionAction.ALLOW, 'mcp.policy.allowed')
        await self.audit.record(control, DecisionAction.AUDIT, 'mcp.discovery_completed')
        return visible

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        definition = next((tool for tool in self.backend.list_tools() if tool.name == name), None)
        control = self.request(definition.operation if definition else 'tool.unknown')
        await self.authorize(control)
        if definition is None:
            await self.block(control, 'mcp.tool.blocked')
        try:
            jsonschema.validate(arguments, definition.input_schema)
            segments = tuple(strings(arguments, (), Source.TOOL_ARGUMENT))
        except Exception:
            await self.block(control, 'mcp.invalid_arguments')
            raise AssertionError('Unreachable')
        guarded = await self.guards.inspect_input(segments)
        if guarded.action == DecisionAction.BLOCK:
            await self.block(control, guarded.reason_code, guarded.identifiers)
        if guarded.action == DecisionAction.REDACT:
            apply_replacements(arguments, guarded.replacements)
            await self.audit.record(control, DecisionAction.REDACT, 'guard.pii.redacted', guarded.identifiers)
        # T07 request-bound approvals and budget reservation enter here.
        await self.audit.record(control, DecisionAction.ALLOW, 'mcp.policy.allowed')
        try:
            value = await self.backend.call_tool(name, arguments)
        except Exception:
            await self.audit.record(control, DecisionAction.AUDIT, 'mcp.backend_failed')
            raise MCPBlocked('mcp.backend_failed') from None
        return await self.inspect_result(control, value, Source.MCP_RESULT)

    async def read_resource(self, uri: str) -> str:
        definition = next((r for r in self.backend.list_resources() if r.uri == uri), None)
        control = self.request(definition.operation if definition else 'resource.unknown')
        await self.authorize(control)
        if definition is None:
            await self.block(control, 'mcp.resource.blocked')
        await self.audit.record(control, DecisionAction.ALLOW, 'mcp.policy.allowed')
        try:
            value = await self.backend.read_resource(uri)
        except Exception:
            await self.audit.record(control, DecisionAction.AUDIT, 'mcp.backend_failed')
            raise MCPBlocked('mcp.backend_failed') from None
        return await self.inspect_result(control, value, Source.RESOURCE_CONTENT)

    async def inspect_result(self, control: ControlRequest, value: str, source: Source) -> str:
        if not isinstance(value, str) or len(value.encode()) > self.guards.settings.output.max_bytes:
            await self.result_block(control, 'guard.output.too_large')
        segment = InspectionSegment('result', value, source, mutable=False, untrusted_external=True)
        guarded = await self.guards.inspect_output((segment,), semantic=True)
        if guarded.action == DecisionAction.BLOCK:
            await self.result_block(control, guarded.reason_code, guarded.identifiers)
        await self.audit.record(control, DecisionAction.AUDIT, 'mcp.backend_completed')
        return value

    async def result_block(self, control: ControlRequest, reason: str, identifiers: tuple[str, ...] = ()) -> None:
        await self.audit.record(control, DecisionAction.BLOCK, reason, identifiers)
        await self.audit.record(control, DecisionAction.AUDIT, 'mcp.result_blocked')
        raise MCPBlocked(reason)
