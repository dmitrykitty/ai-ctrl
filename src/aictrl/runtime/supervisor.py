"""Host-owned lifecycle, deadlines and cleanup for the isolated runtime."""

import json
import os
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pydantic import SecretStr

from aictrl.adapters.base import AgentConfig, EndpointPurpose, RoutingMode
from aictrl.adapters.claude import ClaudeAdapter
from aictrl.adapters.codex import CodexAdapter
from aictrl.contracts import AgentSession, SessionState
from aictrl.runtime.auth import AUTH_CONTAINER, CLAUDE_STATE, AuthenticationCheckError, claude_authenticated
from aictrl.runtime.codex_auth import CODEX_AUTH_CONTAINER, CODEX_STATE, codex_authenticated
from aictrl.runtime.compose import render_compose
from aictrl.runtime.config import ProjectConfig, load_config
from aictrl.runtime.docker import RuntimeDeadline, RuntimeFailure, docker, free_subnet
from aictrl.runtime.workspace import PROJECT_ROOT, validate_workspace
from aictrl.policy.loader import load_policy


@dataclass
class ManagedSession:
    identity: AgentSession
    container_name: str
    deadline: datetime
    container_id: str | None = None


class RuntimeSupervisor:
    def __init__(self, workspace: Path, settings: ProjectConfig, agent: AgentConfig,
                 project: Path = PROJECT_ROOT, *, interactive: bool = False,
                 test_upstream_network: str | None = None) -> None:
        self.workspace = validate_workspace(workspace, project)
        self.settings, self.agent, self.project = settings, agent, project
        self.uid, self.gid = os.getuid(), os.getgid()
        if not self.uid or not self.gid:
            raise RuntimeFailure('Run the host supervisor as a non-root user.')
        now = datetime.now(timezone.utc)
        adapters = {'claude': ClaudeAdapter, 'codex': CodexAdapter}
        if agent.adapter not in adapters:
            raise RuntimeFailure('Unsupported runtime adapter.')
        adapter_type = adapters[agent.adapter]
        if agent.state_mount != adapter_type.state_mount:
            raise RuntimeFailure('A dedicated matching provider state path is required.')
        identity = AgentSession(agent_id=agent.adapter, adapter=agent.adapter, user_id=f'uid-{self.uid}',
                                profile_id='local', workspace=str(self.workspace), protocol=adapter_type.protocol,
                                billing_mode=adapter_type.billing_mode, started_at=now)
        self.gateway_mode = settings.runtime.routing_mode == RoutingMode.APPLICATION_GATEWAY
        if self.gateway_mode:
            identity.session_token = SecretStr(secrets.token_urlsafe(48))
            rendered = adapter_type(agent.image_ref, RoutingMode.APPLICATION_GATEWAY).render_config(identity)
            self.agent = agent.model_copy(update={'environment': dict(agent.environment) | rendered.environment})
        self.identifier = identity.session_id.hex
        self.session = ManagedSession(identity, 'aictrl-' + self.identifier + '-agent', now + timedelta(seconds=settings.limits.wall_time_seconds))
        self._deadline = time.monotonic() + settings.limits.wall_time_seconds
        self.interactive = interactive
        self.test_upstream_network = test_upstream_network
        self.directory = tempfile.TemporaryDirectory(prefix='aictrl-' + self.identifier + '-')
        self.manifest = Path(self.directory.name) / 'compose.json'
        self.compose = ['compose', '--project-name', 'aictrl-' + self.identifier, '--file', str(self.manifest), '--profile', 'runtime']
        self.lock_id: str | None = None
        self.lock_name: str | None = None
        self.stop_signal: int | None = None
        self.process: subprocess.Popen | None = None
        self._prepared = False
        self._closed = False

    def remaining(self) -> float:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeDeadline('Runtime wall-clock deadline exceeded.')
        if self.stop_signal:
            raise RuntimeFailure('Runtime interrupted.')
        return remaining

    def _docker(self, arguments: list[str], timeout: float = 15, *, check: bool = True):
        """All preparation operations consume the same host deadline."""
        try:
            result = docker(arguments, timeout=min(timeout, self.remaining()), check=check)
        except RuntimeFailure:
            self.remaining()
            raise
        return result

    def prepare(self) -> None:
        volume = self.agent.persistent_state_volume
        if not volume:
            raise RuntimeFailure('A dedicated provider state volume is required.')
        if self._docker(['ps', '--filter', 'volume=' + volume, '--format', '{{.ID}}']).stdout.strip():
            raise RuntimeFailure('Provider state is already in use by another container.')
        self._docker(['version', '--format', '{{.Server.Version}}'])
        self._docker(['image', 'inspect', self.agent.image_ref, '--format', '{{.Id}}'])
        self._docker(['image', 'inspect', self.settings.runtime.proxy_image, '--format', '{{.Id}}'])
        if self.gateway_mode:
            self._docker(['image', 'inspect', self.settings.gateway.image, '--format', '{{.Id}}'])
            load_policy(self.project / 'config/policy.yaml')
            raw_audit = self.project / self.settings.gateway.audit_directory
            audit = raw_audit.resolve()
            if raw_audit.is_symlink() or audit != self.project.resolve() / self.settings.gateway.audit_directory or self.workspace == audit or self.workspace in audit.parents:
                raise RuntimeFailure('Audit storage must stay in the protected control directory.')
            audit.mkdir(parents=True, exist_ok=True, mode=0o700)
            audit.chmod(0o700)
        # Reserve the same engine-level name used by authentication operations.
        # This stopped container holds no mounts and prevents concurrent state use.
        lock_name = {CLAUDE_STATE: AUTH_CONTAINER, CODEX_STATE: CODEX_AUTH_CONTAINER}.get(volume, 'aictrl-' + self.identifier + '-state-lock')
        self.lock_name = lock_name
        self.lock_id = self._docker(['create', '--name', lock_name, '--label', 'io.aictrl.session=' + self.identifier,
                               '--label', 'io.aictrl.managed=true', '--network', 'none', '--cap-drop', 'ALL',
                               '--read-only', '--entrypoint', '/bin/true', self.agent.image_ref]).stdout.strip()
        if self._docker(['ps', '--filter', 'volume=' + volume, '--format', '{{.ID}}']).stdout.strip():
            raise RuntimeFailure('Provider state became busy; refusing concurrent use.')
        subnet = free_subnet(self._docker)
        self.proxy_ip = str(subnet[2])
        self.internal_network = 'aictrl-' + self.identifier + '_agent-internal'
        inference_hosts = {endpoint.host for endpoint in self.agent.required_provider_endpoints if endpoint.purpose == EndpointPurpose.INFERENCE}
        endpoints = [endpoint for endpoint in self.agent.required_provider_endpoints
                     if not self.gateway_mode or endpoint.host not in inference_hosts]
        if self.gateway_mode and any(endpoint.host in inference_hosts for endpoint in self.settings.runtime.test_destinations):
            raise RuntimeFailure('Inference destinations cannot be generic proxy test destinations in gateway mode.')
        records = [{'host': endpoint.host, 'port': endpoint.port} for endpoint in endpoints]
        records += [endpoint.model_dump(mode='json', exclude_none=True) for endpoint in self.settings.runtime.test_destinations]
        destination_file = Path(self.directory.name) / 'destinations.json'
        destination_file.write_text(json.dumps(records))
        destination_file.chmod(0o444)
        if self.gateway_mode:
            identity = self.session.identity
            record = {name: str(getattr(identity, name)) for name in ('session_id', 'agent_id', 'adapter', 'user_id', 'profile_id')}
            record['expires_at'] = self.session.deadline.isoformat()
            record['session_token'] = identity.session_token.get_secret_value()
            session_file = Path(self.directory.name) / 'session.json'
            session_file.write_text(json.dumps(record))
            session_file.chmod(0o400)
        topology = render_compose(self.project, Path(self.directory.name), self.workspace, self.settings, self.agent,
                                  self.identifier, str(subnet), self.proxy_ip, self.uid, self.gid, self.interactive,
                                  self.test_upstream_network)
        self.manifest.write_text(json.dumps(topology))
        self._prepared = True
        infrastructure = ['proxy', 'gateway'] if self.gateway_mode else ['proxy']
        self._docker([*self.compose, 'up', '--detach', '--wait', '--wait-timeout', str(max(1, int(min(self.remaining(), 30)))), *infrastructure], timeout=35)

    def _owned(self, identifier: str) -> bool:
        result = docker(['inspect', '--format', '{{index .Config.Labels "io.aictrl.session"}}', identifier], timeout=3, check=False)
        return result.returncode == 0 and result.stdout.strip() == self.identifier

    def _signal_agent(self, sig: str) -> None:
        identifier = self.session.container_id or self.session.container_name
        if self._owned(identifier):
            docker(['kill', '--signal', sig, identifier], timeout=3, check=False)

    def restrict(self) -> None:
        """Future response hook: disconnect only this managed agent's network."""
        identifier = self.session.container_id or self.session.container_name
        if self._owned(identifier):
            docker(['network', 'disconnect', '--force', self.internal_network, identifier])
            self.session.identity.state = SessionState.RESTRICTED

    def terminate(self) -> None:
        """Future response hook: request termination of this session only."""
        self.session.identity.state = SessionState.TERMINATING
        self._signal_agent('SIGTERM')

    def _handle_signal(self, signum, frame) -> None:
        self.stop_signal = signum
        try:
            self._signal_agent(signal.Signals(signum).name)
        except RuntimeFailure:
            pass

    def run(self, command: tuple[str, ...] | None = None, *, input_text: str | None = None,
            capture_output: bool = False) -> tuple[int, str]:
        if input_text is not None and len(input_text.encode()) > 65536:
            raise ValueError('Print-mode input exceeds the 64 KiB host limit.')
        previous = {sig: signal.signal(sig, self._handle_signal) for sig in (signal.SIGINT, signal.SIGTERM)}
        output_file = tempfile.TemporaryFile() if capture_output else None
        input_file = tempfile.TemporaryFile() if input_text is not None else None
        if input_file is not None:
            input_file.write((input_text + '\n').encode())
            input_file.seek(0)
        captured = ''
        result = 1
        try:
            if not self._prepared:
                self.prepare()
            args = ['docker', *self.compose, 'run', '--rm', '--name', self.session.container_name, '--no-deps']
            if not self.interactive:
                args.append('-T')
            args += ['agent', *(command or self.agent.entry_command)]
            self.remaining()
            self.process = subprocess.Popen(args, stdin=input_file,
                                            stdout=output_file, stderr=output_file, start_new_session=True)
            self.session.identity.state = SessionState.ACTIVE
            stopping_at = None
            while self.process.poll() is None:
                if self.session.container_id is None:
                    found = docker(['inspect', '--format', '{{.Id}}', self.session.container_name], timeout=2, check=False)
                    if found.returncode == 0:
                        self.session.container_id = found.stdout.strip()
                if self.stop_signal or time.monotonic() >= self._deadline:
                    if stopping_at is None:
                        stopping_at = time.monotonic()
                        self.terminate()
                    if time.monotonic() - stopping_at >= 3:
                        self._signal_agent('SIGKILL')
                        self.process.terminate()
                        break
                time.sleep(0.1)
            try:
                result = self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                result = 1
            if self.stop_signal:
                result = 128 + self.stop_signal
            elif time.monotonic() >= self._deadline:
                result = 124
            self.session.identity.state = SessionState.TERMINATED if result == 0 else SessionState.FAILED
        except RuntimeDeadline:
            result = 124
            self.session.identity.state = SessionState.FAILED
        except BaseException:
            if self.stop_signal:
                result = 128 + self.stop_signal
                self.session.identity.state = SessionState.FAILED
            else:
                self.session.identity.state = SessionState.FAILED
                raise
        finally:
            try:
                self.close()
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
                self.session.identity.ended_at = datetime.now(timezone.utc)
                if input_file is not None:
                    input_file.close()
                if output_file is not None:
                    output_file.seek(0)
                    captured = output_file.read().decode(errors='replace')
                    output_file.close()
        return result, captured

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        cleanup_error = None
        try:
            if self._prepared:
                identifier = self.session.container_id or self.session.container_name
                if self._owned(identifier):
                    docker(['rm', '--force', identifier], timeout=10, check=False)
                docker([*self.compose, 'down', '--volumes', '--remove-orphans', '--timeout', '3'], timeout=20)
        except RuntimeFailure as error:
            cleanup_error = error
        finally:
            try:
                lock = self.lock_id or self.lock_name
                if lock and self._owned(lock):
                    docker(['rm', '--force', lock], timeout=10)
            finally:
                if self.process is not None and self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=3)
                self.directory.cleanup()
        if cleanup_error:
            raise RuntimeFailure(f'Cleanup failed for managed session {self.identifier}.') from None


def run_agent(name: str, workspace: Path, project: Path = PROJECT_ROOT, *, prompt: str | None = None,
              timeout: int | None = None) -> int:
    selected = validate_workspace(workspace, project)
    settings = load_config(project)
    if timeout is not None:
        if not 1 <= timeout <= settings.limits.wall_time_seconds:
            raise ValueError('Timeout must be positive and no larger than the configured wall-clock limit.')
        settings = settings.model_copy(update={'limits': settings.limits.model_copy(update={'wall_time_seconds': timeout})})
    if name == 'claude':
        provider, adapter_type, authenticated = settings.claude, ClaudeAdapter, claude_authenticated
    elif name == 'codex' and settings.codex is not None:
        provider, adapter_type, authenticated = settings.codex, CodexAdapter, codex_authenticated
        if settings.runtime.routing_mode != RoutingMode.APPLICATION_GATEWAY:
            raise RuntimeFailure('Codex requires APPLICATION_GATEWAY routing.')
    else:
        raise ValueError('Unsupported or unconfigured agent.')
    if not authenticated(provider.image):
        raise AuthenticationCheckError(f'{name.capitalize()} is not authenticated.\nRun:\n    make {name}-login')
    protocol = adapter_type.protocol
    identity = AgentSession(agent_id=name, adapter=name, user_id=f'uid-{os.getuid()}', profile_id='local',
                            workspace=str(selected), protocol=protocol, billing_mode=adapter_type.billing_mode,
                            started_at=datetime.now(timezone.utc))
    adapter = adapter_type(provider.image, RoutingMode.EGRESS_ONLY)
    agent = adapter.render_config(identity)
    runtime = RuntimeSupervisor(selected, settings, agent, project, interactive=prompt is None and sys.stdin.isatty() and sys.stdout.isatty())
    command = agent.entry_command
    if prompt is not None:
        if name == 'claude':
            command = ('claude', '--print', '--output-format', 'text')
        else:
            # Native exec prints its complete input on stderr. Keep diagnostics
            # ephemeral and return only its final answer and exit status.
            command = ('bash', '-c', 'exec "$@" 2>/dev/null', 'aictrl-codex-exec', *adapter.exec_command())
    coverage = f'structured {protocol} admission' if runtime.gateway_mode else 'HTTPS destination enforcement'
    print(f'AICTRL session {runtime.identifier}: {settings.runtime.routing_mode}, {coverage}, UID/GID {runtime.uid}:{runtime.gid}', flush=True)
    result, _ = runtime.run(command, input_text=prompt)
    if result and name == 'codex':
        print('Codex exited unsuccessfully; inspect safe session events for gateway admission.', file=sys.stderr)
    return result


def run_claude(workspace: Path, project: Path = PROJECT_ROOT, *, prompt: str | None = None,
               timeout: int | None = None) -> int:
    return run_agent('claude', workspace, project, prompt=prompt, timeout=timeout)
