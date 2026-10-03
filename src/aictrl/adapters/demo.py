from aictrl.adapters.base import AgentConfig, RoutingMode
from aictrl.contracts import AgentProtocol, AgentSession, BillingMode


class DemoAgentAdapter:
    name = "demo-agent"
    protocol = AgentProtocol.CHAT_COMPLETIONS
    billing_mode = BillingMode.LOCAL
    entry_command = ("python", "/opt/aictrl/demo/agent/main.py")
    persistent_state_volume = None
    state_mount = None
    stateless = True
    environment = {"AICTRL_GATEWAY_URL": "http://gateway:8000", 'AICTRL_ADAPTER': 'demo-agent'}
    required_provider_endpoints = ()

    def __init__(self, image_ref: str, routing_mode: RoutingMode = RoutingMode.APPLICATION_GATEWAY) -> None:
        self.image_ref = image_ref

    def render_config(self, session: AgentSession) -> AgentConfig:
        if session.adapter != self.name or session.session_token is None:
            raise ValueError("session belongs to a different adapter")
        return AgentConfig(
            adapter=self.name,
            image_ref=self.image_ref,
            entry_command=self.entry_command,
            environment=dict(self.environment) | {'AICTRL_SESSION_TOKEN': session.session_token.get_secret_value()},
            stateless=True,
        )

    def smoke_command(self) -> tuple[str, ...]:
        return ("python", "--version")

    def prompt_command(self) -> tuple[str, ...]:
        return self.entry_command
