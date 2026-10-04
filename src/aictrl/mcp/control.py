"""Independent authorization on every operation, before backend execution."""

from datetime import datetime, timezone
from typing import Any
import asyncio
from copy import deepcopy

import jsonschema

from aictrl.contracts import BillingMode, Channel, ControlRequest, DecisionAction, PolicyContext, UsageMetric
from aictrl.gateway.audit import EventRecorder
from aictrl.gateway.inspection import strings
from aictrl.gateway.session import GatewaySession
from aictrl.guards.engine import GuardEngine
from aictrl.guards.models import InspectionSegment, Source, apply_replacements
from aictrl.mcp.backend import MCPBackend
from aictrl.policy.engine import PolicyEngine
from aictrl.reporting.sink import EventSink, StoreFailure
from aictrl.governance.admission import admit, GovernanceBlocked
from aictrl.governance.approvals import request_digest
from aictrl.governance.budgets import BudgetManager
from aictrl.governance.reload import ConfigSnapshot, ConfigSnapshotManager


class MCPBlocked(RuntimeError):
    def __init__(self, reason: str, approval_id=None) -> None:
        self.reason = reason
        self.approval_id = approval_id
        super().__init__('AICTRL MCP operation blocked: ' + reason + ('; approval_id=' + str(approval_id) if approval_id else ''))


class MCPControlService:
    def __init__(self, session: GatewaySession, policy: PolicyEngine, guards: GuardEngine,
                 sink: EventSink, backend: MCPBackend, *, snapshots: ConfigSnapshotManager | None = None,
                 snapshot: ConfigSnapshot | None = None, governance: BudgetManager | None = None) -> None:
        self.session, self.policy, self.guards, self.backend = session, policy, guards, backend
        self.audit = EventRecorder(session, policy.policy.policy_version, sink)
        self.sink, self.snapshots, self.snapshot, self.governance = sink, snapshots, snapshot, governance
        self.context = PolicyContext(session_id=session.session_id, agent_id=session.agent_id,
                                     user_id=session.user_id, profile_id=session.profile_id,
                                     policy_version=policy.policy.policy_version)

    def capture(self):
        if self.snapshots is None:
            return self
        current = self.snapshots.capture()
        return MCPControlService(self.session, current.engine, current.guards, self.sink, self.backend,
                                 snapshot=current, governance=self.governance)

    def request(self, operation: str) -> ControlRequest:
        return ControlRequest(session_id=self.session.session_id, channel='MCP', direction='OUTBOUND',
                              protocol=None, inspection_level='STRUCTURED', target_id='demo-mcp',
                              operation_id=operation, created_at=datetime.now(timezone.utc))

    def allowed(self, operation: str) -> bool:
        return self.policy.decide(self.context, self.request(operation)).action != DecisionAction.BLOCK

    async def block(self, control: ControlRequest, reason: str, identifiers: tuple[str, ...] = ()) -> None:
        await self.audit.record(control, DecisionAction.BLOCK, reason, identifiers)
        raise MCPBlocked(reason)

    async def authorize(self, control: ControlRequest) -> DecisionAction:
        try:
            action = self.policy.decide(self.context, control).action
        except Exception:
            await self.block(control, 'mcp.policy_error')
            return
        if action == DecisionAction.BLOCK:
            await self.block(control, 'mcp.policy.blocked')
        return action

    async def admit(self, control, action, digest):
        try:
            return await admit(self.governance, self.snapshot, self.context, control, action, self.audit, digest=digest)
        except GovernanceBlocked as error:
            raise MCPBlocked(error.reason, error.approval_id) from None

    @staticmethod
    def usage(control):
        return UsageMetric(request_id=control.request_id, session_id=control.session_id,
                           agent_steps=int(control.operation_id.startswith(('tool.', 'resource.'))),
                           tool_calls=int(control.operation_id.startswith('tool.')), billing_mode=BillingMode.LOCAL)

    async def settle(self, reservation, control):
        try:
            await asyncio.shield(asyncio.to_thread(self.governance.store.settle, reservation, self.usage(control)))
        except StoreFailure:
            await self.audit.record(control, DecisionAction.BLOCK, 'governance.store_unavailable')
            raise

    async def list_tools(self):
        if self.snapshots is not None:
            return await self.capture().list_tools()
        control = self.request('tools.list')
        action = await self.authorize(control)
        reservation = await self.admit(control, action, request_digest(self.context, control, {}))
        visible = tuple(tool for tool in self.backend.list_tools() if self.allowed(tool.operation))
        await self.audit.record(control, DecisionAction.AUDIT, 'mcp.discovery_completed')
        await self.settle(reservation, control)
        return visible

    async def list_resources(self):
        if self.snapshots is not None:
            return await self.capture().list_resources()
        control = self.request('resources.list')
        action = await self.authorize(control)
        reservation = await self.admit(control, action, request_digest(self.context, control, {}))
        visible = tuple(resource for resource in self.backend.list_resources() if self.allowed(resource.operation))
        await self.audit.record(control, DecisionAction.AUDIT, 'mcp.discovery_completed')
        await self.settle(reservation, control)
        return visible

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if self.snapshots is not None:
            return await self.capture().call_tool(name, arguments)
        definition = next((tool for tool in self.backend.list_tools() if tool.name == name), None)
        control = self.request(definition.operation if definition else 'tool.unknown')
        action = await self.authorize(control)
        if definition is None:
            await self.block(control, 'mcp.tool.blocked')
        try:
            jsonschema.validate(arguments, definition.input_schema)
            digest = request_digest(self.context, control, arguments)
            arguments = deepcopy(arguments)
            segments = tuple(strings(arguments, (), Source.TOOL_ARGUMENT))
        except Exception:
            await self.block(control, 'mcp.invalid_arguments')
            raise AssertionError('Unreachable')
        guarded = await self.guards.inspect_input(segments, channel=Channel.MCP)
        if guarded.action == DecisionAction.BLOCK:
            await self.block(control, guarded.reason_code, guarded.identifiers)
        if guarded.action == DecisionAction.REDACT:
            apply_replacements(arguments, guarded.replacements)
            await self.audit.record(control, DecisionAction.REDACT, 'guard.pii.redacted', guarded.identifiers)
        # T07: exact approval + all claims + lifetime limits before dispatch.
        reservation = await self.admit(control, action, digest)
        try:
            try:
                value = await self.backend.call_tool(name, arguments)
            except Exception:
                await self.audit.record(control, DecisionAction.AUDIT, 'mcp.backend_failed', usage=self.usage(control))
                raise MCPBlocked('mcp.backend_failed') from None
            return await self.inspect_result(control, value, Source.MCP_RESULT)
        except asyncio.CancelledError:
            await asyncio.shield(self.audit.record(control, DecisionAction.AUDIT, 'mcp.backend_cancelled', usage=self.usage(control)))
            raise
        finally:
            await self.settle(reservation, control)

    async def read_resource(self, uri: str) -> str:
        if self.snapshots is not None:
            return await self.capture().read_resource(uri)
        definition = next((r for r in self.backend.list_resources() if r.uri == uri), None)
        control = self.request(definition.operation if definition else 'resource.unknown')
        action = await self.authorize(control)
        if definition is None:
            await self.block(control, 'mcp.resource.blocked')
        reservation = await self.admit(control, action, request_digest(self.context, control, {'uri': uri}))
        try:
            try:
                value = await self.backend.read_resource(uri)
            except Exception:
                await self.audit.record(control, DecisionAction.AUDIT, 'mcp.backend_failed', usage=self.usage(control))
                raise MCPBlocked('mcp.backend_failed') from None
            return await self.inspect_result(control, value, Source.RESOURCE_CONTENT)
        except asyncio.CancelledError:
            await asyncio.shield(self.audit.record(control, DecisionAction.AUDIT, 'mcp.backend_cancelled', usage=self.usage(control)))
            raise
        finally:
            await self.settle(reservation, control)

    async def inspect_result(self, control: ControlRequest, value: str, source: Source) -> str:
        if not isinstance(value, str) or len(value.encode()) > self.guards.settings.output.max_bytes:
            await self.result_block(control, 'guard.output.too_large')
        segment = InspectionSegment('result', value, source, mutable=False, untrusted_external=True)
        guarded = await self.guards.inspect_output((segment,), semantic=True, channel=Channel.MCP)
        if guarded.action == DecisionAction.BLOCK:
            await self.result_block(control, guarded.reason_code, guarded.identifiers)
        await self.audit.record(control, DecisionAction.AUDIT, 'mcp.backend_completed', usage=self.usage(control))
        return value

    async def result_block(self, control: ControlRequest, reason: str, identifiers: tuple[str, ...] = ()) -> None:
        await self.audit.record(control, DecisionAction.BLOCK, reason, identifiers)
        await self.audit.record(control, DecisionAction.AUDIT, 'mcp.result_blocked')
        raise MCPBlocked(reason)
