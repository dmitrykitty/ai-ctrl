"""One production Codex invocation; retain only safe first-rejection structure.

No live invocation occurs without --live. No retries, synthetic provider,
protocol bypass, raw output logging or provider-state inspection is performed.
Jev is optional for diagnosis of the first response, but required for the full
tool-follow-up qualification. Ordinary runtime cleanup and provider leases apply.
"""

import argparse
import json
from pathlib import Path

from aictrl.adapters.codex import CodexAdapter
from aictrl.reporting.store import EventStore
from aictrl.runtime.config import load_config
from aictrl.runtime.docker import RuntimeFailure, docker
from aictrl.runtime.supervisor import RuntimeSupervisor
from aictrl.runtime.workspace import PROJECT_ROOT


class DiagnosticRuntime(RuntimeSupervisor):
    first_rejection: dict | None = None
    diagnostic_read_failed = False
    gateway_found = False
    gateway_log_bytes = 0

    def close(self) -> None:
        if not self._closed and self._prepared:
            try:
                gateway_id = docker([*self.compose, 'ps', '--all', '--quiet', 'gateway']).stdout.strip()
                if gateway_id:
                    self.gateway_found = True
                    # Logs stay in RAM; only our fixed-vocabulary structural
                    # record survives. Never print the surrounding log lines.
                    logs = docker(['logs', '--tail', '100', gateway_id])
                    self.gateway_log_bytes = len(logs.stdout.encode()) + len(logs.stderr.encode())
                    for line in (logs.stdout + logs.stderr).splitlines():
                        if 'AICTRL_OUTPUT_STRUCTURE ' not in line:
                            continue
                        candidate = json.loads(line.split('AICTRL_OUTPUT_STRUCTURE ', 1)[1])
                        if (candidate.get('schema') == 1
                                and candidate.get('session_id') == str(self.session.identity.session_id)):
                            self.first_rejection = candidate
                            break
            except (RuntimeFailure, ValueError, TypeError, AttributeError):
                self.diagnostic_read_failed = True
        super().close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Run exactly one real invocation; never retry.')
    args = parser.parse_args()
    if not args.live:
        print('Live diagnostic not started. --live runs one real Codex invocation.')
        return 2
    settings = load_config(PROJECT_ROOT)
    settings = settings.model_copy(update={'limits': settings.limits.model_copy(update={'wall_time_seconds': 90})})
    adapter = CodexAdapter(settings.codex.image, settings.runtime.routing_mode)
    runtime = DiagnosticRuntime(PROJECT_ROOT / 'demo/project', settings, adapter)
    directory = Path(runtime.directory.name)
    native_exit = 1
    exact_response = False
    runner_failed = False
    try:
        native_exit, output = runtime.run(adapter.prompt_command(), capture_output=True,
                                         input_text='Read demo_codex.txt using a local tool and reply with exactly its content and nothing else.')
        exact_response = any(line.strip() == 'AICTRL_CODEX_TOOL_OK' for line in output.splitlines())
    except RuntimeFailure:
        runner_failed = True
    finally:
        runtime.close()
    cleanup = {}
    for resource in ('container', 'network', 'volume'):
        command = ['ps', '--all', '--quiet'] if resource == 'container' else [resource, 'ls', '--quiet']
        cleanup[resource] = not docker([*command, '--filter', 'label=io.aictrl.session=' + runtime.identifier]).stdout.strip()
    cleanup['ephemeral_identity_and_key'] = not directory.exists()
    events = EventStore(PROJECT_ROOT / '.aictrl/audit/events.sqlite3').events(runtime.session.identity.session_id)
    report = {
        'purpose': 'structural diagnosis, not a milestone PASS',
        'session': str(runtime.session.identity.session_id),
        'native_exit': native_exit,
        'exact_response': exact_response,
        'runner_failed': runner_failed,
        'diagnostic_read_failed': runtime.diagnostic_read_failed,
        'gateway_found': runtime.gateway_found,
        'gateway_log_bytes': runtime.gateway_log_bytes,
        'first_rejection': runtime.first_rejection,
        'events': [{'action': event.action.value, 'reason': event.reason_code,
                    'event_id': str(event.event_id), 'request_id': str(event.request_id)} for event in events],
        'cleanup': cleanup,
    }
    destination = PROJECT_ROOT / '.aictrl/qualifications/t06-codex-diagnostic.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    safe = json.dumps(report, sort_keys=True, indent=2)
    destination.write_text(safe + '\n')
    print(safe)
    return 0 if runtime.first_rejection is not None and all(cleanup.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
