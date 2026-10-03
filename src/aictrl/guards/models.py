from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aictrl.contracts import DecisionAction, GuardResult


class Source(StrEnum):
    USER_INPUT = 'user_input'
    SYSTEM_INSTRUCTION = 'system_instruction'
    TOOL_RESULT = 'tool_result'
    TOOL_ARGUMENT = 'tool_argument'
    MODEL_OUTPUT = 'model_output'
    MCP_RESULT = 'mcp_result'
    RESOURCE_CONTENT = 'resource_content'


@dataclass(frozen=True)
class InspectionSegment:
    segment_id: str
    text: str = field(repr=False)
    source: Source
    json_path: tuple[str | int, ...] = ()
    mutable: bool = True
    untrusted_external: bool = False


@dataclass(frozen=True)
class Replacement:
    path: tuple[str | int, ...]
    text: str = field(repr=False)


@dataclass(frozen=True)
class GuardEvaluation:
    action: DecisionAction
    results: tuple[GuardResult, ...]
    replacements: tuple[Replacement, ...] = field(default=(), repr=False)

    @property
    def reason_code(self) -> str:
        return next((r.reason_code for r in self.results if r.action == self.action), 'guard.allowed')

    @property
    def identifiers(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(identifier for r in self.results
                                  for identifier in (r.guard_id, *r.signature_ids)))


def aggregate(actions: list[DecisionAction]) -> DecisionAction:
    for action in (DecisionAction.BLOCK, DecisionAction.REQUIRE_APPROVAL, DecisionAction.REDACT):
        if action in actions:
            return action
    return DecisionAction.ALLOW


def apply_replacements(payload: Any, replacements: tuple[Replacement, ...]) -> None:
    for replacement in replacements:
        parent = payload
        for key in replacement.path[:-1]:
            parent = parent[key]
        parent[replacement.path[-1]] = replacement.text
