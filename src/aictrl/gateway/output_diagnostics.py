"""Bounded structural diagnostics: no provider values or arbitrary key names."""

import hashlib
import json
from typing import Any


# Protocol validity and security relevance are separate questions. These lists
# describe the pinned client's roles for diagnostics; they do not admit frames.
GUARDED_EVENTS = frozenset({
    'content_block_start', 'content_block_delta', 'content_block_stop',
    'response.output_item.added', 'response.output_item.done',
    'response.output_text.delta', 'response.output_text.done',
    'response.content_part.added', 'response.content_part.done',
    'response.function_call_arguments.delta', 'response.function_call_arguments.done',
    'response.custom_tool_call_input.delta', 'response.custom_tool_call_input.done',
    'response.reasoning_text.delta', 'response.reasoning_summary_text.delta',
    'response.reasoning_summary_text.done', 'response.reasoning_summary_part.added',
    'response.reasoning_summary_part.done',
})
CONTROL_EVENTS = frozenset({
    'message_start', 'message_delta', 'message_stop', 'ping', 'error',
    'response.created', 'response.in_progress', 'response.completed',
    'response.incomplete', 'response.failed', 'response.metadata',
    'codex.response.metadata',
})
IGNORED_EVENTS = frozenset({'responsesapi.websocket_timing'})
KNOWN_EVENTS = GUARDED_EVENTS | CONTROL_EVENTS | IGNORED_EVENTS
KNOWN_LABELS = KNOWN_EVENTS | {'message'}
KNOWN_ITEM_TYPES = frozenset({
    'message', 'function_call', 'custom_tool_call', 'reasoning',
    'output_text', 'summary_text', 'reasoning_text', 'text', 'tool_use', 'thinking',
})
KNOWN_KEYS = frozenset({
    'type', 'sequence_number', 'output_index', 'item', 'item_id', 'call_id',
    'content_index', 'summary_index', 'delta', 'text', 'arguments', 'input',
    'id', 'name', 'role', 'status', 'content', 'summary', 'encrypted_content',
    'annotations', 'logprobs', 'phase', 'response', 'output', 'usage',
    'error', 'message', 'code', 'param', 'metadata', 'model',
    'index', 'content_block', 'partial_json', 'thinking', 'signature',
})
KNOWN_CONDITIONS = frozenset({
    'unspecified', 'delta.not_string', 'item.invalid_index', 'item.not_object',
    'item.invalid_identifier', 'item.ambiguous_aliases', 'item.duplicate_start',
    'delta.ambiguous_item', 'arguments.not_string', 'arguments.invalid_json',
    'item.ambiguous_done',
})
UNPARSED = object()


def transport_context(headers: Any, status: int) -> dict:
    media = headers.get('content-type', '').split(';', 1)[0].lower()
    known_media = {'text/event-stream', 'application/json', 'text/plain', 'text/html', 'application/octet-stream'}
    encoding = headers.get('content-encoding', 'identity').lower()
    return {
        'http_status': status,
        'selected_format': 'SSE' if media == 'text/event-stream' else 'NON_SSE',
        'media_type': media.strip() if media.strip() in known_media else 'unknown_or_missing',
        'content_type_header_count': len(headers.get_list('content-type')),
        'content_type_has_comma': ',' in media,
        'content_type_has_whitespace': media != media.strip(),
        'content_encoding': encoding if encoding in {'identity', 'gzip', 'br', 'deflate', 'zstd'} else 'unknown',
    }


def kind(value: Any) -> str:
    if value is UNPARSED:
        return 'unparsed'
    if value is None:
        return 'null'
    return {dict: 'object', list: 'array', str: 'string', bool: 'boolean',
            int: 'number', float: 'number'}.get(type(value), 'unknown')


def shape(value: Any, depth: int = 0) -> dict:
    result: dict = {'kind': kind(value)}
    if isinstance(value, dict):
        result['field_count'] = len(value)
        if depth < 2:
            # A key can itself contain credentials/text. Only fixed protocol
            # names survive; unknown names and their values are never hashed.
            known = [name for name in sorted(KNOWN_KEYS) if name in value]
            result['fields'] = {name: shape(value[name], depth + 1) for name in known[:16]}
            result['omitted_known_field_count'] = max(0, len(known) - 16)
            result['unknown_field_count'] = sum(name not in KNOWN_KEYS for name in value)
    elif isinstance(value, list):
        result['length'] = len(value)
        if depth < 2:
            result['sample_shapes'] = [shape(item, depth + 1) for item in value[:4]]
    return result


def known_name(value: Any, allowed: frozenset[str]) -> str:
    if value is UNPARSED:
        return 'unparsed'
    if value is None:
        return 'absent_or_null'
    return value if isinstance(value, str) and value in allowed else 'unknown'


def rejected_frame(*, payload: Any, payload_bytes: int, label: str | None,
                   stage: str, error: BaseException, active_units: int) -> dict:
    layout = shape(payload)
    canonical = json.dumps(layout, sort_keys=True, separators=(',', ':')).encode()
    event = payload.get('type') if isinstance(payload, dict) else UNPARSED
    item = payload.get('item') if isinstance(payload, dict) else None
    name = known_name(event, KNOWN_EVENTS)
    if name in GUARDED_EVENTS:
        role = 'GUARDED_CONTENT'
    elif name in CONTROL_EVENTS:
        role = 'KNOWN_CONTROL_OR_METADATA'
    elif name in IGNORED_EVENTS:
        role = 'KNOWN_IGNORED_BY_PINNED_CODEX'
    else:
        role = 'UNKNOWN'
    return {
        'schema': 1,
        'stage': stage,
        'condition': known_name(getattr(error, 'condition', 'unspecified'), KNOWN_CONDITIONS),
        'error_class': type(error).__name__ if type(error).__name__ in {
            'OutputBlocked', 'ValueError', 'JSONDecodeError', 'UnicodeDecodeError',
            'RecursionError', 'TypeError', 'KeyError', 'AttributeError',
        } else 'unknown',
        'event_label': known_name(label, KNOWN_LABELS),
        'json_type': name,
        'event_role': role,
        'data_is_json': (False if stage == 'json.decode' else None) if payload is UNPARSED else True,
        'payload_bytes': payload_bytes,
        'active_units': active_units,
        'item_type': known_name(item.get('type'), KNOWN_ITEM_TYPES)
                     if isinstance(item, dict) else 'absent_or_invalid',
        'shape': layout,
        'shape_sha256': hashlib.sha256(canonical).hexdigest(),
    }
