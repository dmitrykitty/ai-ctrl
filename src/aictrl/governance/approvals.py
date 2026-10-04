"""Request binding uses RAM-only canonical JSON. No argument storage."""

import hashlib
import json
from uuid import UUID

from aictrl.contracts import ControlRequest, PolicyContext
from aictrl.governance.store import GovernanceStore, ApprovalRecord


def request_digest(context: PolicyContext, request: ControlRequest, arguments: object) -> str:
    identity = {'session': str(context.session_id), 'agent': context.agent_id, 'user': context.user_id,
                'profile': context.profile_id, 'channel': request.channel.value, 'direction': request.direction.value,
                'protocol': request.protocol.value if request.protocol else None, 'target': request.target_id,
                'operation': request.operation_id, 'arguments': arguments}
    canonical = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


class ApprovalManager:
    def __init__(self, store: GovernanceStore) -> None:
        self.store = store

    def list(self, session_id: UUID | None = None) -> list[ApprovalRecord]:
        return self.store.approvals(session_id)

    def approve(self, approval_id: UUID) -> ApprovalRecord | None:
        return self.store.decide_approval(approval_id, approve=True)

    def deny(self, approval_id: UUID) -> ApprovalRecord | None:
        return self.store.decide_approval(approval_id, approve=False)
