"""Bounded native semantic units. Safe units release their original SSE bytes."""

import json
import re
from dataclasses import dataclass, field
from time import monotonic
from typing import Any

from aictrl.gateway.inspection import output_segments, strings, strict_json
from aictrl.gateway.output_diagnostics import UNPARSED, rejected_frame
from aictrl.guards.models import InspectionSegment, Source


class OutputBlocked(RuntimeError):
    def __init__(self, reason: str = 'guard.output.invalid', identifiers: tuple[str, ...] = (),
                 *, diagnostic: dict | None = None, condition: str = 'unspecified') -> None:
        self.reason = reason
        self.identifiers = identifiers
        self.diagnostic = diagnostic
        self.condition = condition
        super().__init__('Provider output withheld.')


@dataclass
class OutputUnit:
    raw: bytes = field(repr=False)
    segments: tuple[InspectionSegment, ...] = field(repr=False)


class SSEOutputBuffer:
    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        self.pending = bytearray()
        self.buffer = bytearray()
        self.values: list[InspectionSegment] = []
        self.deltas: dict[tuple[Any, ...], str] = {}
        self.active: set[Any] = set()
        self.started: float | None = None

    def feed(self, chunk: bytes) -> list[OutputUnit]:
        self.pending.extend(chunk)
        units: list[OutputUnit] = []
        while match := re.search(rb'(?:\r?\n){2}', self.pending):
            frame = bytes(self.pending[:match.end()])
            del self.pending[:match.end()]
            if len(frame) + len(self.buffer) > self.max_bytes:
                raise OutputBlocked('guard.output.too_large')
            lines = frame.splitlines()
            data = b'\n'.join(line[5:].lstrip(b' ') for line in lines if line.startswith(b'data:'))
            payload = UNPARSED
            label = None
            stage = 'sse.label'
            try:
                label = next((line[6:].strip().decode('ascii') for line in lines if line.startswith(b'event:')), None)
                label_segments = tuple(strings(label, (), Source.MODEL_OUTPUT, mutable=False)) if label else ()
                if not data:
                    if self.active:
                        self.buffer.extend(frame)
                        self.values.extend(label_segments)
                    else:
                        units.append(OutputUnit(frame, label_segments))
                    continue
                # The native Responses client dispatches by JSON type, not the
                # optional SSE transport label. A known terminal sentinel carries
                # no model content and cannot close an unfinished inspected unit.
                if data == b'[DONE]':
                    stage = 'sse.sentinel'
                    if self.active or self.buffer:
                        raise OutputBlocked('guard.output.incomplete')
                    units.append(OutputUnit(frame, label_segments))
                    self.started = None
                    continue
                stage = 'json.decode'
                payload = strict_json(data)
                stage = 'json.object'
                if not isinstance(payload, dict):
                    raise ValueError('Invalid SSE object')
                stage = 'event.type'
                event = payload.get('type', label)
                if not isinstance(event, str):
                    raise ValueError('Invalid SSE event')
                if self.started is None:
                    self.started = monotonic()
                self.buffer.extend(frame)
                stage = 'content.extract'
                self.values.extend(output_segments(payload))
                self.values.extend(label_segments)
                stage = 'unit.transition'
                self.transition(event, payload)
                if not self.active:
                    stage = 'unit.arguments'
                    extra = []
                    for key, text in self.deltas.items():
                        extra.extend(strings(text, (), Source.MODEL_OUTPUT, mutable=False))
                        try:
                            extra.extend(strings(strict_json(text), (), Source.MODEL_OUTPUT, mutable=False))
                        except (ValueError, RecursionError):
                            if key[-1] in ('partial_json', 'response.function_call_arguments.delta'):
                                raise OutputBlocked('guard.output.invalid_arguments') from None
                    units.append(OutputUnit(bytes(self.buffer), tuple(self.values + extra)))
                    self.buffer.clear()
                    self.values.clear()
                    self.deltas.clear()
                    self.started = None
            except OutputBlocked as error:
                error.diagnostic = rejected_frame(payload=payload, payload_bytes=len(data), label=label,
                                                  stage=stage, error=error, active_units=len(self.active))
                raise
            except (ValueError, UnicodeError, RecursionError, TypeError, KeyError, AttributeError) as error:
                diagnostic = rejected_frame(payload=payload, payload_bytes=len(data), label=label,
                                            stage=stage, error=error, active_units=len(self.active))
                raise OutputBlocked(diagnostic=diagnostic) from None
        if len(self.pending) + len(self.buffer) > self.max_bytes:
            raise OutputBlocked('guard.output.too_large')
        if self.pending and self.started is None:
            self.started = monotonic()
        return units

    def delta(self, key: tuple[Any, ...], value: Any) -> None:
        if not isinstance(value, str):
            raise OutputBlocked(condition='delta.not_string')
        self.deltas[key] = self.deltas.get(key, '') + value

    def transition(self, event: str, payload: dict) -> None:
        raise NotImplementedError

    def finish(self) -> None:
        if self.pending or self.active or self.buffer:
            raise OutputBlocked('guard.output.incomplete')


class AnthropicOutputBuffer(SSEOutputBuffer):
    def transition(self, event: str, payload: dict) -> None:
        if event == 'content_block_start':
            index = payload.get('index')
            if not isinstance(index, int) or index in self.active:
                raise OutputBlocked()
            self.active.add(index)
            block = payload.get('content_block', {})
            for key in ('text', 'thinking'):
                if key in block:
                    self.delta((index, key), block[key])
        elif event == 'content_block_delta':
            index = payload.get('index')
            if index not in self.active:
                raise OutputBlocked()
            delta = payload.get('delta', {})
            for key in ('text', 'partial_json', 'thinking'):
                if key in delta:
                    self.delta((index, key), delta[key])
        elif event == 'content_block_stop':
            if payload.get('index') not in self.active:
                raise OutputBlocked()
            self.active.remove(payload['index'])
        elif event in ('message_stop', 'error') and self.active:
            raise OutputBlocked('guard.output.incomplete')


class ResponsesOutputBuffer(SSEOutputBuffer):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(max_bytes)
        self.aliases: dict[int, set[tuple[str, int | str]]] = {}
        self.next_item = 0

    @staticmethod
    def identities(payload: dict) -> set[tuple[str, int | str]]:
        aliases: set[tuple[str, int | str]] = set()
        if 'output_index' in payload:
            index = payload['output_index']
            if type(index) is not int or index < 0:
                raise OutputBlocked(condition='item.invalid_index')
            aliases.add(('index', index))
        item = payload.get('item')
        if item is None:
            item = {}
        if not isinstance(item, dict):
            raise OutputBlocked(condition='item.not_object')
        for name, value in (('id', payload.get('item_id')), ('id', item.get('id')),
                            ('call', payload.get('call_id')), ('call', item.get('call_id'))):
            if value is not None:
                if not isinstance(value, str) or not 1 <= len(value) <= 256:
                    raise OutputBlocked(condition='item.invalid_identifier')
                aliases.add((name, value))
        return aliases

    def matching_item(self, aliases: set[tuple[str, int | str]]) -> int | None:
        matches = [key for key in self.active if self.aliases[key] & aliases]
        if len(matches) > 1:
            raise OutputBlocked(condition='item.ambiguous_aliases')
        if matches:
            key = matches[0]
            self.aliases[key].update(aliases)
            return key
        # Legacy native frames may omit indexes/IDs. Only one active item
        # can supply an unambiguous boundary in that case.
        if len(self.active) == 1:
            key = next(iter(self.active))
            if not aliases or not self.aliases[key]:
                self.aliases[key].update(aliases)
                return key
        return None

    def start_item(self, aliases: set[tuple[str, int | str]]) -> int:
        key = self.next_item
        self.next_item += 1
        self.aliases[key] = aliases
        self.active.add(key)
        return key

    def transition(self, event: str, payload: dict) -> None:
        if event == 'response.output_item.added':
            identities = self.identities(payload)
            if self.matching_item(identities) is not None:
                raise OutputBlocked(condition='item.duplicate_start')
            index = self.start_item(identities)
            item = payload.get('item', {})
            if item.get('type') == 'function_call' and item.get('arguments') is not None:
                self.delta((index, 0, 'response.function_call_arguments.delta'), item['arguments'])
            for content_index, block in enumerate(item.get('content') or []):
                if isinstance(block, dict) and block.get('text') is not None:
                    self.delta((index, content_index, 'response.output_text.delta'), block['text'])
        elif event.endswith('.delta'):
            identities = self.identities(payload)
            index = self.matching_item(identities)
            if index is None:
                if not identities and self.active:
                    raise OutputBlocked(condition='delta.ambiguous_item')
                # A native item can begin with deltas, without an added frame.
                # Keep it withheld until its matching complete item arrives.
                index = self.start_item(identities)
            self.delta((index, payload.get('content_index', payload.get('summary_index', 0)), event), payload.get('delta'))
        elif event == 'response.output_item.done':
            item = payload.get('item', {})
            if item.get('type') == 'function_call':
                arguments = item.get('arguments')
                if not isinstance(arguments, str):
                    raise OutputBlocked('guard.output.invalid_arguments', condition='arguments.not_string')
                try:
                    strict_json(arguments)
                except (ValueError, RecursionError):
                    raise OutputBlocked('guard.output.invalid_arguments', condition='arguments.invalid_json') from None
            identities = self.identities(payload)
            index = self.matching_item(identities)
            if index is not None:
                self.active.remove(index)
                del self.aliases[index]
            elif not identities and self.active:
                raise OutputBlocked(condition='item.ambiguous_done')
            # Done-only frames contain a complete native item and are checked
            # as a whole. They cannot close another unidentified active item.
        elif event in ('response.completed', 'response.failed', 'response.incomplete', 'error') and self.active:
            raise OutputBlocked('guard.output.incomplete')
