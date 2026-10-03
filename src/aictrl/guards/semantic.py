"""Narrow semantic boundary; probabilities and content are never audit data."""

from dataclasses import dataclass, field
from typing import Protocol

from aictrl.guards.models import InspectionSegment

QUESTIONS = ('prompt_injection', 'data_exfiltration', 'security_bypass')


class SemanticUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__('Semantic provider unavailable.')


@dataclass(frozen=True)
class SemanticAssessment:
    probabilities: dict[str, float] = field(repr=False)
    model: str = 'jev-latest'
    input_tokens: int = 0
    output_tokens: int = 0


class SemanticDecisionProvider(Protocol):
    async def evaluate(self, segments: tuple[InspectionSegment, ...]) -> SemanticAssessment: ...
