"""Validate mounts without changing ownership or reading credential contents."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def validate_workspace(workspace: Path, project: Path = PROJECT_ROOT) -> Path:
    try:
        selected = workspace.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ValueError("Workspace does not exist or cannot be resolved.") from None
    if not selected.is_dir():
        raise ValueError("Workspace must be a directory.")
    home = Path.home().resolve()
    controls = [project.resolve(), Path('/var/lib/docker'), Path('/run'), Path('/etc'), Path('/proc'), Path('/sys'), Path('/dev')]
    controls += [home / name for name in ('.ssh', '.aws', '.kube', '.claude', '.codex', '.agents', '.config')]
    # A demo workspace inside this source checkout is explicitly supported.
    control_project = project.resolve()
    for control in controls:
        if control == control_project:
            if selected == control or selected in control.parents:
                raise ValueError("Workspace overlaps AICTRL control files; choose demo/project or a separate repository.")
            if control in selected.parents and not (control / 'demo/project' == selected or control / 'demo/project' in selected.parents):
                raise ValueError("Workspace is an AICTRL control directory.")
        elif selected == control or control in selected.parents or selected in control.parents:
            raise ValueError("Workspace overlaps a protected host directory.")
    if selected == Path('/tmp') or selected == Path('/'):
        raise ValueError("Workspace overlaps host runtime control storage.")
    for name in ('.ssh', '.aws', '.kube', '.claude', '.codex', '.git/ssh', '.aictrl'):
        if (selected / name).exists():
            raise ValueError("Workspace contains a protected credential or control directory.")
    return selected
