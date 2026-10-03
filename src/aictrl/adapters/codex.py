from aictrl.adapters.base import AgentConfig, EndpointPurpose, ProviderEndpoint, RoutingMode
from aictrl.contracts import AgentSession


class CodexAdapter:
    name = 'codex'
    entry_command = ('codex', '--no-daemon', '--profile', 'aictrl')
    persistent_state_volume = 'aictrl-codex-state'
    state_mount = '/home/dev/.codex'
    environment = {
        'AICTRL_ADAPTER': 'codex', 'CODEX_HOME': '/home/dev/.codex',
        'HTTP_PROXY': 'http://proxy:8080', 'HTTPS_PROXY': 'http://proxy:8080',
        'NO_PROXY': 'gateway,localhost,127.0.0.1',
        'CODEX_CA_CERTIFICATE': '/etc/ssl/certs/ca-certificates.crt',
    }
    required_provider_endpoints = (
        ProviderEndpoint(host='api.openai.com', purpose=EndpointPurpose.INFERENCE),
        ProviderEndpoint(host='chatgpt.com', purpose=EndpointPurpose.INFERENCE),
        ProviderEndpoint(host='auth.openai.com', purpose=EndpointPurpose.AUTHENTICATION),
    )

    def __init__(self, image_ref: str, routing_mode: RoutingMode = RoutingMode.APPLICATION_GATEWAY) -> None:
        self.image_ref, self.routing_mode = image_ref, RoutingMode(routing_mode)

    def render_config(self, session: AgentSession) -> AgentConfig:
        if session.adapter != self.name or session.protocol != 'RESPONSES':
            raise ValueError('session belongs to a different adapter or protocol')
        environment = dict(self.environment)
        if self.routing_mode == RoutingMode.APPLICATION_GATEWAY:
            if session.session_token is None:
                raise ValueError('supervisor must supply an internal session token')
            environment['AICTRL_SESSION_TOKEN'] = session.session_token.get_secret_value()
        return AgentConfig(adapter=self.name, image_ref=self.image_ref, entry_command=self.entry_command,
                           persistent_state_volume=self.persistent_state_volume, state_mount=self.state_mount,
                           environment=environment, required_provider_endpoints=self.required_provider_endpoints)

    def smoke_command(self) -> tuple[str, ...]:
        return ('codex', '--version')

    def exec_command(self) -> tuple[str, ...]:
        return (*self.entry_command, 'exec', '--skip-git-repo-check', '--ephemeral', '--color', 'never')
