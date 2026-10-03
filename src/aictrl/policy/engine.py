"""Provider-independent exact matching: BLOCK wins, then ALLOW, else BLOCK."""

from aictrl.contracts import ControlDecision, ControlRequest, DecisionAction, PolicyContext
from aictrl.policy.models import Policy


class PolicyEngine:
    def __init__(self, policy: Policy) -> None:
        self.policy = policy

    def decide(self, context: PolicyContext, request: ControlRequest) -> ControlDecision:
        agent = self.policy.agents.get(context.agent_id)
        allowed = False
        if (context.session_id == request.session_id and context.policy_version == self.policy.policy_version
                and agent is not None and agent.enabled):
            for rule in agent.rules:
                if (rule.channel == request.channel and rule.direction == request.direction
                        and rule.protocol == request.protocol and rule.target == request.target_id
                        and request.operation_id in rule.operations and rule.inspection_level == request.inspection_level):
                    if rule.action == 'BLOCK':
                        allowed = False
                        break
                    allowed = True
        return ControlDecision(request_id=request.request_id,
                               action=DecisionAction.ALLOW if allowed else DecisionAction.BLOCK,
                               reason_code=str(request.channel).lower() + ('.policy.allowed' if allowed else '.policy.blocked'),
                               policy_version=self.policy.policy_version)
