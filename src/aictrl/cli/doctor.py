import shutil
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import ValidationError

from aictrl.runtime.config import ProjectConfig


@dataclass(frozen=True)
class Check:
    status: Literal["OK", "WARN", "FAIL"]
    name: str
    detail: str


def docker_check(name: str, args: list[str], *, optional: bool = False) -> Check:
    try:
        result = subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return Check("WARN" if optional else "FAIL", name, "unavailable or timed out")
    if result.returncode:
        # Do not dump subprocess errors or environment into logs.
        return Check("WARN" if optional else "FAIL", name, "unavailable")
    return Check("OK", name, result.stdout.strip())


def inspect_environment(project: Path) -> list[Check]:
    checks = [
        Check(
            "OK" if sys.version_info[:2] == (3, 12) else "FAIL",
            "Python",
            f"{sys.version.split()[0]} (required: 3.12)",
        )
    ]
    if shutil.which("docker") is None:
        checks.append(Check("FAIL", "Docker", "executable not found"))
    else:
        checks.append(
            docker_check("Docker daemon", ["version", "--format", "{{.Server.Version}}"])
        )
        checks.append(docker_check("Docker Compose", ["compose", "version", "--short"]))

    configuration = None
    try:
        configuration = ProjectConfig.model_validate(
            yaml.safe_load((project / "config/project.yaml").read_text())
        )
    except (OSError, yaml.YAMLError, ValidationError):
        checks.append(Check("FAIL", "configuration", "config/project.yaml is missing or invalid"))
    else:
        checks.append(Check("OK", "configuration", "config/project.yaml validated"))

    required = ("src/aictrl", "docker", "config", "demo", "tests", "scripts", "docs")
    missing = [directory for directory in required if not (project / directory).is_dir()]
    checks.append(
        Check("FAIL", "directories", ", ".join(missing))
        if missing
        else Check("OK", "directories", "required project directories available")
    )
    if configuration is not None and shutil.which("docker") is not None:
        checks.append(
            docker_check(
                "Claude runtime image",
                ["image", "inspect", configuration.claude.image, "--format", "{{.Id}}"],
                optional=True,
            )
        )
        checks.append(
            docker_check(
                "Runtime proxy image",
                ["image", "inspect", configuration.runtime.proxy_image, "--format", "{{.Id}}"],
                optional=True,
            )
        )
        if configuration.runtime.routing_mode == 'APPLICATION_GATEWAY':
            checks.append(docker_check('Native gateway image', ['image', 'inspect', configuration.gateway.image, '--format', '{{.Id}}'], optional=True))
    checks.append(Check('OK' if os.environ.get('AICTRL_JEV_API_KEY') else 'WARN', 'Semantic provider',
                        'configured' if os.environ.get('AICTRL_JEV_API_KEY') else
                        'unavailable; requests requiring semantic inspection will fail closed'))
    return checks
