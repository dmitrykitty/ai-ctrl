import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from aictrl.contracts import AgentProtocol, Identifier


class GatewaySession(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    session_id: UUID
    agent_id: Identifier
    adapter: Identifier
    protocol: AgentProtocol | None
    user_id: Identifier
    profile_id: Identifier
    expires_at: AwareDatetime
    session_token: SecretStr = Field(exclude=True, repr=False)

    @field_validator('session_token')
    @classmethod
    def strong_token(cls, value: SecretStr) -> SecretStr:
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', value.get_secret_value()):
            raise ValueError('Invalid session token')
        return value

    def accepts(self, values: list[str]) -> bool:
        return (len(values) == 1 and len(values[0]) <= 256
                and self.expires_at > datetime.now(timezone.utc)
                and secrets.compare_digest(values[0].encode(), self.session_token.get_secret_value().encode()))


def load_session(path: Path) -> GatewaySession:
    try:
        return GatewaySession.model_validate_json(path.read_text())
    except (OSError, ValidationError):
        raise ValueError('Trusted session configuration is missing or invalid.') from None
