from pathlib import Path

import yaml
from pydantic import ValidationError

from aictrl.policy.models import Policy


def load_policy(path: Path) -> Policy:
    try:
        candidate = yaml.safe_load(path.read_text())
        if isinstance(candidate, dict) and candidate.get('schema_version') in (1, 2):
            raise ValueError('Policy schema ' + str(candidate['schema_version']) + ' is unsupported; configuration schema 3 is required.')
        return Policy.model_validate(candidate)
    except (OSError, yaml.YAMLError, ValidationError):
        raise ValueError('Policy is missing or invalid.') from None
