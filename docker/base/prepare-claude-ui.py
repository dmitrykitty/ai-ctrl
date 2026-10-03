"""Set one non-secret native UI preference after host authentication preflight.

Native auth login does not complete interactive onboarding. The configuration
file is edited in place inside the provider volume; credential files are never
opened, exported, or changed. Workspace trust remains a native user decision.
"""

import json
import os
from pathlib import Path

path = Path('/home/dev/.claude/.claude.json')
try:
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+', encoding='utf-8') as config_file:
        text = config_file.read(1024 * 1024 + 1)
        if len(text) > 1024 * 1024:
            raise ValueError('oversized configuration')
        config = json.loads(text) if text.strip() else {}
        if not isinstance(config, dict):
            raise ValueError('invalid configuration')
        if config.get('hasCompletedOnboarding') is not True:
            config['hasCompletedOnboarding'] = True
            config_file.seek(0)
            json.dump(config, config_file)
            config_file.truncate()
except (OSError, ValueError):
    raise SystemExit('Native Claude UI preferences could not be prepared safely.') from None
