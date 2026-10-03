from aictrl.contracts import AgentProtocol, Channel, ControlDecision, ControlRequest, DecisionAction, Direction, InspectionLevel, PolicyContext
from aictrl.policy.models import Policy


class PolicyEngine:
    def __init__(self, policy: Policy) -> None:
        self.policy = policy

    def decide(self, context: PolicyContext, request: ControlRequest) -> ControlDecision:
        agent = self.policy.agents.get(context.agent_id)
        allowed = (
            context.session_id == request.session_id
            and context.policy_version == self.policy.policy_version
            and agent is not None and agent.enabled
            and request.channel == Channel.LLM and request.direction == Direction.OUTBOUND
            and request.protocol == AgentProtocol.ANTHROPIC_MESSAGES
            and request.inspection_level == InspectionLevel.STRUCTURED
            and request.target_id == 'anthropic'
            and request.operation_id in ('messages', 'count_tokens')
            and getattr(self.policy.llm, request.operation_id, 'BLOCK') == 'ALLOW'
        )
        return ControlDecision(request_id=request.request_id,
                               action=DecisionAction.ALLOW if allowed else DecisionAction.BLOCK,
                               reason_code='llm.policy.allowed' if allowed else 'llm.policy.blocked',
                               policy_version=self.policy.policy_version)
