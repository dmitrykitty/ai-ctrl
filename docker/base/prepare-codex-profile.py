"""Install a public provider profile without opening native credential files."""
import os
import stat
from pathlib import Path

source = Path('/usr/local/share/aictrl/aictrl.config.toml').read_bytes()
path = '/home/dev/.codex/aictrl.config.toml'
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, 'wb') as target:
    metadata = os.fstat(target.fileno())
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise SystemExit('Unsafe Codex provider profile')
    os.ftruncate(target.fileno(), 0)
    os.fchmod(target.fileno(), 0o600)
    target.write(source)
