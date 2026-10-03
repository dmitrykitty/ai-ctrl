from aictrl.adapters.base import AgentConfig
from aictrl.contracts import AgentSession


class DemoAgentAdapter:
    name = "demo-agent"
    entry_command = ("python", "/opt/aictrl/demo/agent/main.py")
    persistent_state_volume = None
    state_mount = None
    environment = {"AICTRL_GATEWAY_URL": "http://gateway:8000"}
    required_provider_endpoints = ()

    def __init__(self, image_ref: str) -> None:
        self.image_ref = image_ref

    def render_config(self, session: AgentSession) -> AgentConfig:
        if session.adapter != self.name:
            raise ValueError("session belongs to a different adapter")
        return AgentConfig(
            adapter=self.name,
            image_ref=self.image_ref,
            entry_command=self.entry_command,
            environment=dict(self.environment),
        )

    def smoke_command(self) -> tuple[str, ...]:
        return ("python", "--version")
