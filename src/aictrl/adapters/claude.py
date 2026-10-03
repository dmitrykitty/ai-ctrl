from aictrl.adapters.base import AgentConfig, EndpointPurpose, ProviderEndpoint
from aictrl.contracts import AgentSession


class ClaudeAdapter:
    name = "claude"
    entry_command = ("claude",)
    persistent_state_volume = "aictrl-claude-state"
    state_mount = "/home/dev/.claude"
    environment = {
        "CLAUDE_CONFIG_DIR": "/home/dev/.claude",
        "ANTHROPIC_BASE_URL": "http://gateway:8000/anthropic",
        "HTTP_PROXY": "http://proxy:8080",
        "HTTPS_PROXY": "http://proxy:8080",
        "NO_PROXY": "gateway,localhost,127.0.0.1",
        "NODE_EXTRA_CA_CERTS": "/etc/aictrl/proxy-ca.pem",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_UPDATES": "1",
        "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
    }
    required_provider_endpoints = (
        ProviderEndpoint(host="api.anthropic.com", purpose=EndpointPurpose.INFERENCE),
        ProviderEndpoint(host="claude.ai", purpose=EndpointPurpose.AUTHENTICATION),
        ProviderEndpoint(host="claude.com", purpose=EndpointPurpose.AUTHENTICATION),
        ProviderEndpoint(host="platform.claude.com", purpose=EndpointPurpose.AUTHENTICATION),
        ProviderEndpoint(host="console.anthropic.com", purpose=EndpointPurpose.AUTHENTICATION),
    )

    def __init__(self, image_ref: str) -> None:
        self.image_ref = image_ref

    def render_config(self, session: AgentSession) -> AgentConfig:
        if session.adapter != self.name:
            raise ValueError("session belongs to a different adapter")
        if session.session_token is None:
            raise ValueError("supervisor must supply an internal session token")
        environment = dict(self.environment)
        environment["ANTHROPIC_CUSTOM_HEADERS"] = (
            "X-AICtrl-Session: " + session.session_token.get_secret_value()
        )
        return AgentConfig(
            adapter=self.name,
            image_ref=self.image_ref,
            entry_command=self.entry_command,
            persistent_state_volume=self.persistent_state_volume,
            state_mount=self.state_mount,
            environment=environment,
            required_provider_endpoints=self.required_provider_endpoints,
        )

    def smoke_command(self) -> tuple[str, ...]:
        return ("claude", "--version")
