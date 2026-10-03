"""Named conservative signatures, without entropy guessing or match logging."""

import re

SIGNATURES = (
    ('secret.pem_private_key', r'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----'),
    ('secret.aws_access_key', r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    ('secret.anthropic_api_key', r'\bsk-ant-[A-Za-z0-9_-]{20,}'),
    ('secret.openai_api_key', r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}'),
    ('secret.github_token', r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})'),
    ('secret.bearer', r'(?i)\bBearer[ \t]+[A-Za-z0-9][A-Za-z0-9._~+/-]{19,}={0,2}'),
    ('secret.synthetic', r'\bAICTRL_SECRET_[A-Za-z0-9_-]+'),
)


class SecretGuard:
    def __init__(self) -> None:
        self.signatures = tuple((name, re.compile(pattern)) for name, pattern in SIGNATURES)

    def scan(self, text: str) -> tuple[str, ...]:
        return tuple(name for name, pattern in self.signatures if pattern.search(text))
