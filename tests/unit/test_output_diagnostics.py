import asyncio
import json
import subprocess
import sys

import httpx
import pytest

from aictrl.gateway.output import OutputBlocked, ResponsesOutputBuffer
from aictrl.gateway.output_diagnostics import rejected_frame, shape, transport_context
from test_gateway import Frames, fixture, invoke
from test_output_guards import frame


@pytest.mark.parametrize('payload,label', [
    ({'type': 'AICTRL_SECRET_event', 'AICTRL_SECRET_key': 'AICTRL_SECRET_value'}, 'AICTRL_SECRET_label'),
    ({'type': 'response.output_item.added', 'item': {'type': 'AICTRL_SECRET_type',
      'id': 'AICTRL_SECRET_id', 'arguments': 'AICTRL_SECRET_arguments',
      'content': [{'text': 'AICTRL_SECRET_text', 'AICTRL_SECRET_nested': 'AICTRL_SECRET_result'}]}}, 'message'),
])
def test_structural_diagnostic_never_retains_values_or_unknown_keys(payload, label):
    diagnostic = rejected_frame(payload=payload, payload_bytes=180, label=label,
                                stage='unit.transition', error=ValueError('AICTRL_SECRET_error'), active_units=1)
    encoded = json.dumps(diagnostic)
    assert 'AICTRL_SECRET_' not in encoded
    assert diagnostic['data_is_json'] is True
    assert len(diagnostic['shape_sha256']) == 64
    assert diagnostic['payload_bytes'] == 180
    assert diagnostic['error_class'] == 'ValueError'


def test_shape_hash_depends_on_structure_not_values_or_unknown_names():
    first = {'type': 'response.output_item.done', 'item': {'type': 'reasoning',
             'id': 'first-private-id', 'content': None, 'private-field-one': 'private-one'}}
    second = {'type': 'response.output_item.done', 'item': {'type': 'reasoning',
              'id': 'different-private-id', 'content': None, 'different-private-field': 'different-private-value'}}
    def digest(payload):
        return rejected_frame(payload=payload, payload_bytes=200, label='message', stage='unit.transition',
                              error=TypeError(), active_units=1)['shape_sha256']
    assert digest(first) == digest(second)
    second['item']['content'] = []
    assert digest(first) != digest(second)


def test_structure_depth_and_array_samples_are_bounded():
    payload = {'item': {'content': [{'text': 'secret'}] * 10000}, 'output': [{'content': ['secret']}] * 10000}
    layout = shape(payload)
    assert layout['fields']['item']['fields']['content'] == {'kind': 'array', 'length': 10000}
    samples = layout['fields']['output']['sample_shapes']
    assert len(samples) == 4
    assert 'secret' not in json.dumps(layout)
    assert len(json.dumps(layout)) < 2000


@pytest.mark.parametrize('raw,stage,is_json', [
    (b'event: message\ndata: {broken AICTRL_SECRET_json\n\n', 'json.decode', False),
    (b'event: message\ndata: []\n\n', 'json.object', True),
    (b'event: message\ndata: {"type":null,"text":"AICTRL_SECRET_body"}\n\n', 'event.type', True),
])
def test_invalid_frame_attaches_structure_without_changing_fail_closed(raw, stage, is_json):
    buffer = ResponsesOutputBuffer(1048576)
    with pytest.raises(OutputBlocked) as error:
        buffer.feed(raw)
    assert error.value.reason == 'guard.output.invalid'
    diagnostic = error.value.diagnostic
    assert diagnostic['stage'] == stage and diagnostic['data_is_json'] is is_json
    assert 'AICTRL_SECRET_' not in json.dumps(diagnostic)
    assert str(error.value) == 'Provider output withheld.'


def test_transition_error_identifies_known_frame_and_types_only():
    raw = frame('response.output_item.added', output_index=None,
                item={'type': 'reasoning', 'id': 'AICTRL_SECRET_identifier', 'content': None})
    buffer = ResponsesOutputBuffer(1048576)
    with pytest.raises(OutputBlocked) as error:
        buffer.feed(raw)
    diagnostic = error.value.diagnostic
    assert error.value.reason == 'guard.output.invalid'
    assert diagnostic['stage'] == 'unit.transition'
    assert diagnostic['condition'] == 'item.invalid_index'
    assert diagnostic['event_role'] == 'GUARDED_CONTENT'
    assert diagnostic['json_type'] == 'response.output_item.added'
    assert diagnostic['item_type'] == 'reasoning'
    assert diagnostic['shape']['fields']['output_index'] == {'kind': 'null'}
    assert 'AICTRL_SECRET_identifier' not in json.dumps(diagnostic)


def test_diagnostics_do_not_admit_an_unknown_content_bearing_delta():
    raw = frame('response.AICTRL_SECRET_unknown.delta', item_id='private-id',
                delta={'text': 'AICTRL_SECRET_private_text'})
    buffer = ResponsesOutputBuffer(1048576)
    with pytest.raises(OutputBlocked) as error:
        buffer.feed(raw)
    diagnostic = error.value.diagnostic
    assert error.value.reason == 'guard.output.invalid'
    assert diagnostic['condition'] == 'delta.not_string'
    assert diagnostic['json_type'] == 'unknown' and diagnostic['event_role'] == 'UNKNOWN'
    assert 'AICTRL_SECRET_' not in json.dumps(diagnostic)


def test_diagnostic_logging_preserves_durable_block_and_never_logs_raw_frame(tmp_path, caplog):
    # Deliberately malformed Anthropic unit; secret values are withheld before
    # the guard can evaluate them. Logs must remain safe on the parser failure.
    raw = frame('content_block_delta', index=0,
                delta={'type': 'text_delta', 'text': 'AICTRL_SECRET_private_body'},
                **{'AICTRL_SECRET_private_key': 'user@example.com'})
    app, store, session, calls, client = fixture(tmp_path, frames=Frames([raw, raw]))
    response = asyncio.run(invoke(app, client))
    assert response.content == b''
    diagnostics = [record.message for record in caplog.records if 'AICTRL_OUTPUT_STRUCTURE ' in record.message]
    assert len(diagnostics) == 1
    diagnostic = json.loads(diagnostics[0].split('AICTRL_OUTPUT_STRUCTURE ', 1)[1])
    assert diagnostic['session_id'] == str(session.session_id)
    assert diagnostic['json_type'] == 'content_block_delta'
    assert diagnostic['shape']['unknown_field_count'] == 1
    assert 'AICTRL_SECRET_' not in caplog.text and 'user@example.com' not in caplog.text
    events = store.events(session.session_id)
    assert [event.action for event in events] == ['ALLOW', 'BLOCK', 'AUDIT']
    assert events[1].reason_code == 'guard.output.invalid'
    assert events[-1].reason_code == 'llm.output_blocked'
    assert 'AICTRL_SECRET_' not in store.path.read_text(errors='ignore')


@pytest.mark.parametrize('response_type', ['application/json', 'text/event-stream, text/event-stream',
                                         'text/event-stream ', 'AICTRL_SECRET_private_media_type'])
def test_non_sse_failure_is_diagnosed_without_header_or_body_values(tmp_path, caplog, response_type):
    raw = b'data: {"type":"response.created","text":"AICTRL_SECRET_private_body"}\n\n'
    app, store, session, calls, client = fixture(tmp_path, frames=Frames([raw]), response_type=response_type)
    response = asyncio.run(invoke(app, client))
    assert response.content == b''
    diagnostics = [record.message for record in caplog.records if 'AICTRL_OUTPUT_STRUCTURE ' in record.message]
    assert len(diagnostics) == 1
    diagnostic = json.loads(diagnostics[0].split('AICTRL_OUTPUT_STRUCTURE ', 1)[1])
    assert diagnostic['stage'] == 'json.decode'
    assert diagnostic['data_is_json'] is False
    assert diagnostic['transport']['selected_format'] == 'NON_SSE'
    assert diagnostic['transport']['content_type_has_comma'] == (',' in response_type)
    assert diagnostic['payload_bytes'] == len(raw)
    assert 'AICTRL_SECRET_' not in caplog.text
    events = store.events(session.session_id)
    assert [event.action for event in events] == ['ALLOW', 'BLOCK', 'AUDIT']
    assert events[1].reason_code == 'guard.output.invalid'


def test_transport_context_excludes_arbitrary_and_credential_headers():
    headers = httpx.Headers([('content-type', 'text/event-stream'), ('content-type', 'text/event-stream'),
                             ('authorization', 'Bearer AICTRL_SECRET_private'),
                             ('content-encoding', 'AICTRL_SECRET_encoding')])
    context = transport_context(headers, 200)
    assert context['content_type_header_count'] == 2
    assert context['content_type_has_comma'] and context['selected_format'] == 'NON_SSE'
    assert context['content_encoding'] == 'unknown'
    assert 'AICTRL_SECRET_' not in json.dumps(context)


def test_production_uvicorn_logging_configuration_emits_structural_warning():
    code = """
import logging
from uvicorn import Config
Config('aictrl.gateway.app:from_environment', log_level='warning').configure_logging()
logging.getLogger('aictrl.gateway').warning('AICTRL_OUTPUT_STRUCTURE {"schema":1,"stage":"unit.transition"}')
"""
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True, timeout=10)
    assert 'AICTRL_OUTPUT_STRUCTURE ' in result.stderr
