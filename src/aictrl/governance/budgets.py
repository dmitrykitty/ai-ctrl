"""All applicable scopes/dimensions plus session lifetime limits form one claim."""

from aictrl.contracts import Channel, ControlRequest, PolicyContext
from aictrl.governance.store import Admission, BudgetClaim, GovernanceStore
from aictrl.policy.models import GovernanceSettings


class BudgetManager:
    def __init__(self, store: GovernanceStore) -> None:
        self.store = store

    @staticmethod
    def claims(context: PolicyContext, request: ControlRequest, settings: GovernanceSettings,
               *, token_reservation: int = 0) -> tuple[BudgetClaim, ...]:
        amounts = {'requests': 0, 'agent_steps': 0, 'tool_calls': 0, 'tokens': 0}
        if request.channel == Channel.LLM:
            amounts.update(requests=1, agent_steps=1, tokens=token_reservation)
        elif request.channel == Channel.MCP:
            if request.operation_id.startswith('tool.'):
                amounts.update(tool_calls=1, agent_steps=1)
            elif request.operation_id.startswith('resource.'):
                amounts['agent_steps'] = 1
        scopes = {'session': str(context.session_id), 'agent': context.agent_id,
                  'user': context.user_id, 'profile': context.profile_id}
        claims = [BudgetClaim(rule.id, rule.scope, scopes[rule.scope], rule.dimension, rule.limit,
                              rule.window_seconds, amounts[rule.dimension]) for rule in settings.budgets if amounts[rule.dimension]]
        for dimension, limit in (('agent_steps', settings.runaway.max_agent_steps),
                                 ('tool_calls', settings.runaway.max_tool_calls)):
            if amounts[dimension]:
                claims.append(BudgetClaim('runaway.' + dimension, 'session', str(context.session_id),
                                          dimension, limit, 0, amounts[dimension]))
        return tuple(claims)

    def reserve(self, context: PolicyContext, request: ControlRequest, settings: GovernanceSettings,
                *, snapshot_key: str, token_reservation: int = 0, approval_digest: str | None = None) -> Admission:
        return self.store.reserve(self.claims(context, request, settings, token_reservation=token_reservation),
            session_id=context.session_id, request_id=request.request_id, policy_version=context.policy_version,
            snapshot_key=snapshot_key, approval_digest=approval_digest, operation_id=request.operation_id,
            approval_ttl=settings.approval_ttl_seconds)
