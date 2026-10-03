import json
import subprocess

import pytest

from aictrl.runtime import auth


@pytest.mark.parametrize("logged_in, native_code, expected", [(True, 0, 0), (False, 1, 1)])
def test_native_status_reports_only_boolean_and_preserves_isolation(monkeypatch, capsys, logged_in, native_code, expected):
    commands = []
    private_diagnostic = "synthetic-private-provider-diagnostic"

    def run(command, **kwargs):
        commands.append(command)
        if command[1] == "ps":
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, native_code, json.dumps({"loggedIn": logged_in, "diagnostic": private_diagnostic}), private_diagnostic)

    monkeypatch.setattr(auth.subprocess, "run", run)
    assert auth.main() == expected
    output = capsys.readouterr()
    assert private_diagnostic not in output.out + output.err
    command = commands[1]
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert "0:0" in command
    assert '--bounding-set=-all' in auth.STATUS_COMMAND
    assert '--inh-caps=-all --ambient-caps=-all --no-new-privs' in auth.STATUS_COMMAND
    assert "type=volume,source=aictrl-claude-state,target=/home/dev/.claude,readonly" in command
    assert command[-3:] == [auth.CLAUDE_IMAGE, "-ec", auth.STATUS_COMMAND]
    assert not any("type=bind" in argument for argument in command)


@pytest.mark.parametrize("output, code", [("not-json", 1), ('{"loggedIn":"yes"}', 0), ('{"loggedIn":true}', 1), ('{"loggedIn":false}', 125)])
def test_status_errors_do_not_trigger_reauthentication(monkeypatch, capsys, output, code):
    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "", "") if command[1] == "ps" else subprocess.CompletedProcess(command, code, output, "synthetic-private-error")
    monkeypatch.setattr(auth.subprocess, "run", run)
    assert auth.main() == 2
    assert "synthetic-private-error" not in capsys.readouterr().out


def test_active_state_is_not_mounted_again(monkeypatch):
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "active-container\n", "")
    monkeypatch.setattr(auth.subprocess, "run", run)
    with pytest.raises(auth.AuthenticationCheckError, match="in use"):
        auth.claude_authenticated()
    assert len(commands) == 1
