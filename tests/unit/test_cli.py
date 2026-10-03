import subprocess
from pathlib import Path

from typer.testing import CliRunner

from aictrl.cli.main import app

ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def fake_docker(monkeypatch, *, daemon_ok=True, image_ok=True):
    monkeypatch.setattr("aictrl.cli.doctor.shutil.which", lambda name: "/usr/bin/docker")
    def command(args, **kwargs):
        ok = daemon_ok if args[1] == "version" else image_ok if args[1] == "image" else True
        return subprocess.CompletedProcess(args, 0 if ok else 1, "verified" if ok else "", "sensitive stderr")
    monkeypatch.setattr("aictrl.cli.doctor.subprocess.run", command)


def test_help_and_run_do_not_start_containers(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("T01 run must not invoke Docker")
    monkeypatch.setattr("subprocess.run", fail_if_called)
    assert runner.invoke(app, ["--help"]).exit_code == 0
    result = runner.invoke(app, ["run", "claude", "."])
    assert result.exit_code == 2
    assert "runtime not implemented yet" in result.output


def test_doctor_image_warning_is_not_required_failure(monkeypatch):
    fake_docker(monkeypatch, image_ok=False)
    result = runner.invoke(app, ["doctor", "--project", str(ROOT)])
    assert result.exit_code == 0
    assert "[WARN] Claude runtime image" in result.output
    assert "sensitive stderr" not in result.output


def test_doctor_required_prerequisite_failure_is_nonzero(monkeypatch):
    fake_docker(monkeypatch, daemon_ok=False)
    result = runner.invoke(app, ["doctor", "--project", str(ROOT)])
    assert result.exit_code == 1
    assert "[FAIL] Docker daemon" in result.output


def test_invalid_configuration_is_nonzero_and_not_dumped(monkeypatch, tmp_path):
    fake_docker(monkeypatch)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/project.yaml").write_text("schema_version: 1\nsecret: synthetic-sensitive-content\n")
    result = runner.invoke(app, ["doctor", "--project", str(tmp_path)])
    assert result.exit_code == 1
    assert "[FAIL] configuration" in result.output
    assert "synthetic-sensitive-content" not in result.output
