import json
import pytest

from aictrl.gateway.usage import AnthropicUsage, ResponsesUsage, requested_reservation
from test_governance import identities


def frame(payload):
    return b'event: usage\ndata: ' + json.dumps(payload).encode() + b'\n\n'


@pytest.mark.parametrize('bad', [-1, True, 1.5, '10', None, 1_000_000_001])
def test_untrustworthy_usage_never_releases_reservation(bad):
    context, request = identities()
    usage = AnthropicUsage('messages')
    usage.observe(frame({'type': 'message_start', 'message': {'usage': {'input_tokens': bad, 'output_tokens': 0}}}))
    usage.observe(frame({'type': 'message_delta', 'usage': {'output_tokens': 2}}))
    usage.observe(frame({'type': 'message_stop'}))
    assert usage.metric(request) is None


def test_synthetic_responses_usage_all_chunk_widths_no_payload_persistence():
    _, request = identities()
    raw = frame({'type': 'response.completed', 'response': {'usage': {'input_tokens': 10, 'output_tokens': 3, 'total_tokens': 13},
                                                         'unrelated': 'private provider text'}})
    for width in (1, 7, 65536):
        usage = ResponsesUsage('responses')
        for offset in range(0, len(raw), width):
            usage.observe(raw[offset:offset + width])
        metric = usage.metric(request)
        assert metric.input_tokens == 10 and metric.output_tokens == 3
        assert 'private provider text' not in metric.model_dump_json()


def test_anthropic_partial_final_cumulative_and_count_operation():
    _, request = identities()
    usage = AnthropicUsage('messages')
    usage.observe(frame({'type': 'message_start', 'message': {'usage': {'input_tokens': 7, 'output_tokens': 0}}}))
    usage.observe(frame({'type': 'message_stop'}))
    assert usage.metric(request) is None  # initial output zero is not final usage
    count = AnthropicUsage('count_tokens')
    count.observe_json({'input_tokens': 12})
    assert count.metric(request).input_tokens == 12 and count.metric(request).output_tokens == 0
    invalid = ResponsesUsage('responses')
    invalid.observe_json({'type': 'response.completed', 'response': {'usage': {'input_tokens': 2, 'output_tokens': 3, 'total_tokens': 99}}})
    assert invalid.metric(request) is None


def test_reservation_uses_known_limit_with_input_allowance_or_configured_fallback():
    assert requested_reservation({'max_tokens': 100}, 'max_tokens', 20, 5) == 105
    for invalid in (-1, True, '100', 1.5, None):
        assert requested_reservation({'max_tokens': invalid}, 'max_tokens', 20, 5) == 25
