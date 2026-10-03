"""Host-only ephemeral semantic key staging; Compose receives the path only."""

import os
from pathlib import Path


def stage_jev_key(directory: Path) -> Path | None:
    key = os.environ.get('AICTRL_JEV_API_KEY')
    if not key:
        return None
    if len(key) > 4096 or not key.isascii() or any(c.isspace() for c in key):
        raise ValueError('Semantic provider key input is invalid.')
    path = directory / 'jev_api_key'
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(descriptor, 'w') as secret:
        secret.write(key)
    return path
