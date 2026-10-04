"""Bounded deterministic feed. Regex uses a deliberately restricted grammar."""

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from aictrl.contracts import Channel, DecisionAction, Identifier, ThreatSignature
from aictrl.policy.models import PolicyModel


def safe_regex(pattern: str) -> re.Pattern[str]:
    # No repetition, alternation, groups, lookarounds, backreferences or inline
    # flags. Character classes, anchors, dots and safe escapes are supported.
    # Work is bounded by feed/pattern/text sizes, with no nested backtracking.
    in_class = False
    escaped = False
    for char in pattern:
        if escaped:
            if char.isdigit() or (char.isalpha() and char not in 'dDsSwWbBnrt'):
                raise ValueError('Unsupported regex escape.')
            escaped = False
        elif char == '\\':
            escaped = True
        elif in_class:
            if char == ']':
                in_class = False
            elif char == '[':
                raise ValueError('Nested regex class.')
        elif char == '[':
            in_class = True
        elif char in '()|*+?{}':
            raise ValueError('Unsupported regex operator.')
    if escaped or in_class:
        raise ValueError('Incomplete regex.')
    try:
        return re.compile(pattern)
    except re.error:
        raise ValueError('Invalid regex.') from None


class FeedSignature(ThreatSignature):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, validate_assignment=False)
    pattern: str = Field(min_length=1, max_length=256)
    kind: Literal['literal', 'regex']
    action: Literal[DecisionAction.BLOCK] = DecisionAction.BLOCK
    channels: tuple[Channel, ...] = Field(min_length=1, strict=False)

    @model_validator(mode='after')
    def valid_pattern(self):
        if self.kind == 'regex':
            safe_regex(self.pattern)
        return self


class ThreatFeed(PolicyModel):
    schema_version: Literal[1] = 1
    feed_version: Identifier = 'initial'
    signatures: tuple[FeedSignature, ...] = Field(default=(), max_length=128, strict=False)

    @model_validator(mode='after')
    def unique_ids(self):
        ids = [signature.signature_id for signature in self.signatures]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate threat IDs.')
        return self


def load_feed(path: Path) -> ThreatFeed:
    try:
        if path.stat().st_size > 131072:
            raise ValueError('Feed too large.')
        # JSON mode retains strict numeric/boolean validation while accepting
        # serialized enum values and tuples in the existing contract shape.
        return ThreatFeed.model_validate_json(path.read_bytes())
    except (OSError, ValueError):
        raise ValueError('Threat feed is missing or invalid.') from None


class ThreatFeedGuard:
    def __init__(self, feed: ThreatFeed) -> None:
        self.feed = feed
        self.signatures = tuple((signature, safe_regex(signature.pattern) if signature.kind == 'regex' else None)
                                for signature in feed.signatures if signature.enabled)

    def scan(self, text: str, channel: Channel) -> tuple[str, ...]:
        return tuple('threat.' + signature.signature_id for signature, pattern in self.signatures
                     if channel in signature.channels and
                     (pattern.search(text) if pattern else signature.pattern in text))
