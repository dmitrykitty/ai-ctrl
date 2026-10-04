"""Provider-independent exact matching: BLOCK > REQUIRE_APPROVAL > ALLOW."""

from aictrl.contracts import ControlDecision, ControlRequest, DecisionAction, PolicyContext
from aictrl.policy.models import Policy


class PolicyEngine:
    def __init__(self, policy: Policy) -> None:
        self.policy = policy

    def decide(self, context: PolicyContext, request: ControlRequest) -> ControlDecision:
        agent = self.policy.agents.get(context.agent_id)
        action = DecisionAction.BLOCK
        if (context.session_id == request.session_id and context.policy_version == self.policy.policy_version
                and agent is not None and agent.enabled):
            matches = []
            for rule in agent.rules:
                if (rule.channel == request.channel and rule.direction == request.direction
                        and rule.protocol == request.protocol and rule.target == request.target_id
                        and request.operation_id in rule.operations and rule.inspection_level == request.inspection_level):
                    matches.append(rule.action)
            for candidate in ('BLOCK', 'REQUIRE_APPROVAL', 'ALLOW'):
                if candidate in matches:
                    action = DecisionAction(candidate)
                    break
        return ControlDecision(request_id=request.request_id,
                               action=action,
                               reason_code=str(request.channel).lower() + {
                                   DecisionAction.ALLOW: '.policy.allowed',
                                   DecisionAction.BLOCK: '.policy.blocked',
                                   DecisionAction.REQUIRE_APPROVAL: '.policy.approval_required'}[action],
                               policy_version=self.policy.policy_version)
