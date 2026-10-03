from pathlib import Path

import yaml
from pydantic import ValidationError

from aictrl.policy.models import Policy


def load_policy(path: Path) -> Policy:
    try:
        return Policy.model_validate(yaml.safe_load(path.read_text()))
    except (OSError, yaml.YAMLError, ValidationError):
        raise ValueError('Policy is missing or invalid.') from None
