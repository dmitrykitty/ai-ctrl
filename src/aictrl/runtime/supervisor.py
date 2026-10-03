"""Host-owned lifecycle, deadlines and cleanup for the isolated runtime."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aictrl.adapters.base import AgentConfig, RoutingMode
from aictrl.adapters.claude import ClaudeAdapter
from aictrl.contracts import AgentSession, SessionState
from aictrl.runtime.auth import AUTH_CONTAINER, CLAUDE_STATE, AuthenticationCheckError, claude_authenticated
from aictrl.runtime.compose import render_compose
from aictrl.runtime.config import ProjectConfig, load_config
from aictrl.runtime.docker import RuntimeDeadline, RuntimeFailure, docker, free_subnet
from aictrl.runtime.workspace import PROJECT_ROOT, validate_workspace


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
        identity = AgentSession(agent_id=agent.adapter, adapter=agent.adapter, user_id=f'uid-{self.uid}',
                                profile_id='local', workspace=str(self.workspace), protocol='ANTHROPIC_MESSAGES',
                                billing_mode='SUBSCRIPTION', started_at=now)
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
        if not volume or self.agent.state_mount != '/home/dev/.claude':
            raise RuntimeFailure('A dedicated Claude state volume is required.')
        if self._docker(['ps', '--filter', 'volume=' + volume, '--format', '{{.ID}}']).stdout.strip():
            raise RuntimeFailure('Claude state is already in use by another container.')
        self._docker(['version', '--format', '{{.Server.Version}}'])
        self._docker(['image', 'inspect', self.agent.image_ref, '--format', '{{.Id}}'])
        self._docker(['image', 'inspect', self.settings.runtime.proxy_image, '--format', '{{.Id}}'])
        # Reserve the same engine-level name used by authentication operations.
        # This stopped container holds no mounts and prevents concurrent state use.
        lock_name = AUTH_CONTAINER if volume == CLAUDE_STATE else 'aictrl-' + self.identifier + '-state-lock'
        self.lock_name = lock_name
        self.lock_id = self._docker(['create', '--name', lock_name, '--label', 'io.aictrl.session=' + self.identifier,
                               '--label', 'io.aictrl.managed=true', '--network', 'none', '--cap-drop', 'ALL',
                               '--read-only', '--entrypoint', '/bin/true', self.agent.image_ref]).stdout.strip()
        if self._docker(['ps', '--filter', 'volume=' + volume, '--format', '{{.ID}}']).stdout.strip():
            raise RuntimeFailure('Claude state became busy; refusing concurrent use.')
        subnet = free_subnet(self._docker)
        self.proxy_ip = str(subnet[2])
        self.internal_network = 'aictrl-' + self.identifier + '_agent-internal'
        records = [{'host': endpoint.host, 'port': endpoint.port} for endpoint in self.agent.required_provider_endpoints]
        records += [endpoint.model_dump(mode='json', exclude_none=True) for endpoint in self.settings.runtime.test_destinations]
        destination_file = Path(self.directory.name) / 'destinations.json'
        destination_file.write_text(json.dumps(records))
        destination_file.chmod(0o444)
        topology = render_compose(self.project, Path(self.directory.name), self.workspace, self.settings, self.agent,
                                  self.identifier, str(subnet), self.proxy_ip, self.uid, self.gid, self.interactive,
                                  self.test_upstream_network)
        self.manifest.write_text(json.dumps(topology))
        self._prepared = True
        self._docker([*self.compose, 'up', '--detach', '--wait', '--wait-timeout', str(max(1, int(min(self.remaining(), 30)))), 'proxy'], timeout=35)

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


def run_claude(workspace: Path, project: Path = PROJECT_ROOT, *, prompt: str | None = None,
               timeout: int | None = None) -> int:
    selected = validate_workspace(workspace, project)
    settings = load_config(project)
    if settings.runtime.routing_mode != RoutingMode.EGRESS_ONLY:
        raise RuntimeFailure('The application gateway is not configured; use EGRESS_ONLY.')
    if timeout is not None:
        if not 1 <= timeout <= settings.limits.wall_time_seconds:
            raise ValueError('Timeout must be positive and no larger than the configured wall-clock limit.')
        settings = settings.model_copy(update={'limits': settings.limits.model_copy(update={'wall_time_seconds': timeout})})
    if not claude_authenticated(settings.claude.image):
        raise AuthenticationCheckError('Claude is not authenticated.\nRun:\n    make claude-login')
    identity = AgentSession(agent_id='claude', adapter='claude', user_id=f'uid-{os.getuid()}', profile_id='local',
                            workspace=str(selected), protocol='ANTHROPIC_MESSAGES', billing_mode='SUBSCRIPTION',
                            started_at=datetime.now(timezone.utc))
    agent = ClaudeAdapter(settings.claude.image, RoutingMode.EGRESS_ONLY).render_config(identity)
    runtime = RuntimeSupervisor(selected, settings, agent, project, interactive=prompt is None and sys.stdin.isatty() and sys.stdout.isatty())
    command = ('claude', '--print', '--output-format', 'text') if prompt is not None else agent.entry_command
    print(f'AICTRL session {runtime.identifier}: EGRESS_ONLY, HTTPS destination enforcement, UID/GID {runtime.uid}:{runtime.gid}', flush=True)
    result, _ = runtime.run(command, input_text=prompt)
    return result
