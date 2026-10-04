"""One shared commit boundary for LLM send and MCP backend execution."""

import asyncio
from typing import Protocol
from uuid import UUID

from aictrl.contracts import ControlRequest, DecisionAction, PolicyContext
from aictrl.governance.budgets import BudgetManager
from aictrl.governance.reload import ConfigSnapshot
from aictrl.governance.store import GovernanceFailure, Reservation


class Recorder(Protocol):
    async def record(self, request: ControlRequest, action: DecisionAction, reason: str,
                     identifiers: tuple[str, ...] = ()) -> None: ...


class GovernanceBlocked(RuntimeError):
    def __init__(self, reason: str, approval_id: UUID | None = None) -> None:
        self.reason, self.approval_id = reason, approval_id
        super().__init__('AICTRL governance blocked.')


async def admit(manager: BudgetManager | None, snapshot: ConfigSnapshot | None, context: PolicyContext,
                request: ControlRequest, action: DecisionAction, audit: Recorder, *,
                digest: str | None = None, token_reservation: int = 0) -> Reservation:
    if manager is None or snapshot is None or (action == DecisionAction.REQUIRE_APPROVAL and digest is None):
        await audit.record(request, DecisionAction.BLOCK, 'governance.store_unavailable')
        raise GovernanceFailure()
    pending = asyncio.create_task(asyncio.to_thread(manager.reserve, context, request, snapshot.policy.governance,
        snapshot_key=snapshot.key, token_reservation=token_reservation,
        approval_digest=digest if action == DecisionAction.REQUIRE_APPROVAL else None))
    try:
        admission = await asyncio.shield(pending)
    except asyncio.CancelledError:
        admission = await pending
        if admission.reservation:
            await asyncio.shield(asyncio.to_thread(manager.store.cancel, admission.reservation))
        raise
    except GovernanceFailure:
        await audit.record(request, DecisionAction.BLOCK, 'governance.store_unavailable')
        raise
    if admission.reason:
        required = admission.reason == 'governance.approval.required'
        await audit.record(request, DecisionAction.REQUIRE_APPROVAL if required else DecisionAction.BLOCK,
                           admission.reason, ('approval.' + str(admission.approval_id),) if admission.approval_id else ())
        raise GovernanceBlocked(admission.reason, admission.approval_id)
    reservation = admission.reservation
    assert reservation is not None
    try:
        # Budget + approval commit happened first. The durable admission event
        # and dispatch-intent commit must both succeed before any side effect.
        await audit.record(request, DecisionAction.ALLOW, request.channel.value.lower() + '.policy.allowed')
        await asyncio.shield(asyncio.to_thread(manager.store.dispatch, reservation))
    except BaseException:
        await asyncio.shield(asyncio.to_thread(manager.store.cancel, reservation))
        raise
    return reservation
