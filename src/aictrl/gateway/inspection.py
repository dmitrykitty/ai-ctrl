"""Ephemeral helpers for native structured content; never used for audit."""

import json
from typing import Any

from aictrl.guards.models import InspectionSegment, Source


def strings(value: Any, path: tuple[str | int, ...], source: Source, *, untrusted: bool = False,
            mutable: bool = True) -> list[InspectionSegment]:
    output: list[InspectionSegment] = []
    def visit(item: Any, location: tuple[str | int, ...], depth: int = 0) -> None:
        if depth > 64 or len(output) > 10000:
            raise ValueError('Inspection structure exceeds bounds.')
        if isinstance(item, str):
            output.append(InspectionSegment(str(len(output)), item, source, location, mutable, untrusted))
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, (*location, index), depth + 1)
        elif isinstance(item, dict):
            for key, child in item.items():
                output.append(InspectionSegment(str(len(output)), key, source, (*location, key), False, untrusted))
                visit(child, (*location, key), depth + 1)
        elif type(item) in (int, float):
            output.append(InspectionSegment(str(len(output)), str(item), source, location, False, untrusted))
    visit(value, path)
    return output


def argument_strings(value: Any, path: tuple[str | int, ...]) -> list[InspectionSegment]:
    segments = strings(value, path, Source.TOOL_ARGUMENT)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, RecursionError):
            return segments
        # Decoded escapes must not hide credentials/PII. If only the decoded
        # form contains PII, withhold rather than corrupt serialized arguments.
        segments.extend(segment for segment in strings(decoded, path, Source.TOOL_ARGUMENT, mutable=False)
                        if segment.text not in value)
    return segments


def output_segments(value: Any) -> tuple[InspectionSegment, ...]:
    segments = strings(value, (), Source.MODEL_OUTPUT, mutable=False)
    decoded_segments = []
    for segment in segments:
        try:
            decoded = strict_json(segment.text)
            decoded_segments.extend(strings(decoded, (), Source.MODEL_OUTPUT, mutable=False))
        except (ValueError, RecursionError):
            pass
    return tuple(segments + decoded_segments)


def text_content(value: Any, path: tuple[str | int, ...], source: Source,
                 *, untrusted: bool = False) -> list[InspectionSegment]:
    if isinstance(value, str):
        return strings(value, path, source, untrusted=untrusted)
    segments: list[InspectionSegment] = []
    if isinstance(value, list):
        for index, block in enumerate(value):
            location = (*path, index)
            if isinstance(block, dict):
                if isinstance(block.get('text'), str):
                    segments.extend(strings(block['text'], (*location, 'text'), source, untrusted=untrusted))
                if block.get('type') == 'tool_result':
                    segments.extend(text_content(block.get('content'), (*location, 'content'), Source.TOOL_RESULT, untrusted=True))
                if block.get('type') == 'tool_use' and 'input' in block:
                    segments.extend(argument_strings(block['input'], (*location, 'input')))
    return segments


def strict_json(raw: bytes | bytearray | str) -> Any:
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise ValueError('Duplicate JSON field.')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Nonfinite JSON number.')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
