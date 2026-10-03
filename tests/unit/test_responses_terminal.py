import pytest

from aictrl.gateway.sse import ResponsesTerminal


@pytest.mark.parametrize('width', [1, 2, 7, 256, 65536])
def test_terminal_frame_across_chunks_and_large_data_is_bounded(width):
    terminal = ResponsesTerminal()
    frame = b'event: response.completed\r\ndata: {"output":"' + b'x'*10000 + b'"}\r\n\r\n'
    for offset in range(0,len(frame),width):
        terminal.observe(frame[offset:offset+width])
        assert len(terminal._prefix) <= 128
    assert terminal.completed and not terminal.failed


@pytest.mark.parametrize('frame', [b'event: response.completed\n', b'event: response.completed\n\n',
                                   b'data: contains response.completed text\n\n',
                                   b'event: response.completed\ndata: incomplete'])
def test_incomplete_or_text_only_marker_is_not_completion(frame):
    terminal = ResponsesTerminal(); terminal.observe(frame)
    assert not terminal.completed


def test_native_error_has_priority_over_a_later_completion():
    terminal = ResponsesTerminal()
    terminal.observe(b'event: response.failed\ndata: {}\n\nevent: response.completed\ndata: {}\n\n')
    assert terminal.failed
