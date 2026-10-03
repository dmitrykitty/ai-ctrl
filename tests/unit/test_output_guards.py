import asyncio
import json

import httpx
import pytest

from aictrl.gateway.anthropic import AnthropicMessagesHandler
from aictrl.gateway.responses import ResponsesHandler
from aictrl.gateway.output import OutputBlocked
from aictrl.gateway.control import ControlPipeline
from aictrl.guards.engine import GuardEngine
from aictrl.policy.models import GuardSettings, OutputSettings
from test_gateway import Frames, fixture, invoke


def frame(kind, **fields):
    return ('event: '+kind+'\ndata: '+json.dumps({'type':kind,**fields})+'\n\n').encode()


def anthropic(parts, *, tool=False):
    return [frame('message_start'),frame('content_block_start',index=0,content_block={'type':'tool_use' if tool else 'text','text':''} if not tool else {'type':'tool_use','input':{}}),
            *(frame('content_block_delta',index=0,delta={'type':'input_json_delta','partial_json':part} if tool else {'type':'text_delta','text':part}) for part in parts),
            frame('content_block_stop',index=0),frame('message_stop')]


def responses(parts, *, tool=False):
    return [frame('response.created'),frame('response.output_item.added',output_index=0,item={'type':'function_call','arguments':''} if tool else {'type':'message','content':[]}),
            *(frame('response.function_call_arguments.delta' if tool else 'response.output_text.delta',output_index=0,content_index=0,delta=part) for part in parts),
            frame('response.output_item.done',output_index=0,item={'type':'function_call','arguments':''.join(parts)} if tool else {'type':'message','content':[{'type':'output_text','text':''.join(parts)}]}),
            frame('response.completed',response={'output':[]})]


async def inspect(handler, chunks, *, settings=None):
    # Exercise the same production inspection generator without HTTP/network.
    pipeline=object.__new__(ControlPipeline)
    pipeline.handler=handler
    pipeline.guards=GuardEngine(settings or GuardSettings())
    response=httpx.Response(200,stream=Frames(chunks),headers={'content-type':'text/event-stream'})
    emitted=[]
    try:
        async for chunk in pipeline.inspect_stream(response):
            emitted.append(chunk)
    except OutputBlocked as error:
        return b''.join(emitted),error.reason
    return b''.join(emitted),None


@pytest.mark.parametrize('handler,maker',[(AnthropicMessagesHandler(),anthropic),(ResponsesHandler(),responses)])
@pytest.mark.parametrize('width',[1,7,65536])
@pytest.mark.parametrize('tool',[False,True])
def test_safe_sse_units_preserve_original_bytes(handler,maker,width,tool):
    frames=maker(['{"cmd":','"pwd"}'] if tool else ['ordinary ','safe text'],tool=tool)
    raw=b''.join(frames)
    emitted,reason=asyncio.run(inspect(handler,[raw[n:n+width] for n in range(0,len(raw),width)]))
    assert reason is None and emitted==raw


@pytest.mark.parametrize('handler,maker',[(AnthropicMessagesHandler(),anthropic),(ResponsesHandler(),responses)])
@pytest.mark.parametrize('parts,expected', [(['AICTRL_SEC','RET_demo123'],'guard.secret.detected'),
                                         (['user@','example.com'],'guard.pii.output_blocked')])
def test_unsafe_split_text_is_withheld(handler,maker,parts,expected):
    frames=maker(parts)
    emitted,reason=asyncio.run(inspect(handler,frames))
    assert reason==expected
    assert emitted==frames[0]
    assert all(part.encode() not in emitted for part in parts)


@pytest.mark.parametrize('handler,maker',[(AnthropicMessagesHandler(),anthropic),(ResponsesHandler(),responses)])
def test_complete_tool_arguments_guarded_including_json_escapes(handler,maker):
    frames=maker(['{"cmd":"AICTRL_','\\u0053ECRET_demo"}'],tool=True)
    emitted,reason=asyncio.run(inspect(handler,frames))
    assert reason=='guard.secret.detected' and emitted==frames[0]


@pytest.mark.parametrize('handler,maker',[(AnthropicMessagesHandler(),anthropic),(ResponsesHandler(),responses)])
def test_oversized_or_incomplete_output_is_fail_closed(handler,maker):
    settings=GuardSettings(output=OutputSettings(max_bytes=1024))
    emitted,reason=asyncio.run(inspect(handler,maker(['x'*2048]),settings=settings))
    assert reason=='guard.output.too_large'
    frames=maker(['safe text'])
    emitted,reason=asyncio.run(inspect(handler,frames[:-2]))
    assert reason=='guard.output.incomplete' and emitted==frames[0]


def test_output_block_is_durable_and_never_completion(tmp_path,caplog):
    frames=anthropic(['AICTRL_SEC','RET_demo123'])
    app,store,session,calls,client=fixture(tmp_path,frames=Frames(frames))
    response=asyncio.run(invoke(app,client))
    assert response.content==frames[0]
    events=store.events(session.session_id)
    assert [event.action for event in events]==['ALLOW','BLOCK','AUDIT']
    assert events[-1].reason_code=='llm.output_blocked'
    assert len({event.request_id for event in events})==1
    assert b'AICTRL_SECRET_demo123' not in store.path.read_bytes()
    assert 'AICTRL_SECRET_demo123' not in caplog.text


def test_unit_deadline_applies_even_while_provider_sends_heartbeats():
    async def proof():
        class Delayed(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield anthropic(['safe'])[1]
                await asyncio.sleep(.2)
                yield frame('ping')
        settings=GuardSettings(output=OutputSettings(timeout_ms=100))
        pipeline=object.__new__(ControlPipeline)
        pipeline.handler=AnthropicMessagesHandler()
        pipeline.guards=GuardEngine(settings)
        response=httpx.Response(200,stream=Delayed(),headers={'content-type':'text/event-stream'})
        with pytest.raises(OutputBlocked,match='withheld') as error:
            async for chunk in pipeline.inspect_stream(response):
                raise AssertionError('An incomplete unit was released.')
        assert error.value.reason=='guard.output.timeout'
    asyncio.run(proof())


def test_missing_anthropic_terminal_never_records_completion(tmp_path):
    from test_gateway import FRAMES
    app,store,session,calls,client=fixture(tmp_path,frames=Frames(FRAMES[:-1]))
    response=asyncio.run(invoke(app,client))
    assert response.content==b''.join(FRAMES[:-1])
    assert store.events(session.session_id)[-1].reason_code=='llm.upstream_failed'


@pytest.mark.parametrize('handler,maker',[(AnthropicMessagesHandler(),anthropic),(ResponsesHandler(),responses)])
def test_malformed_complete_tool_json_is_withheld(handler,maker):
    frames=maker(['{"cmd":'],tool=True)
    emitted,reason=asyncio.run(inspect(handler,frames))
    assert reason=='guard.output.invalid_arguments' and emitted==frames[0]


def test_codex_item_ids_reasoning_custom_tools_and_done_only_snapshots():
    frames = [frame('response.created'),
              frame('response.output_item.added', item={'type':'reasoning','id':'reason_1','content':None}),
              frame('response.reasoning_summary_text.delta', item_id='reason_1', summary_index=0, delta='Reading a public fixture.'),
              frame('response.output_item.done', item={'type':'reasoning','id':'reason_1','summary':[]}),
              frame('response.output_item.added', item={'type':'custom_tool_call','id':'tool_1','call_id':'call_1','input':''}),
              frame('response.custom_tool_call_input.delta', item_id='tool_1', call_id='call_1', delta='cat demo_codex.txt'),
              frame('response.output_item.done', item={'type':'custom_tool_call','id':'tool_1','call_id':'call_1','input':'cat demo_codex.txt'}),
              frame('response.output_item.done', item={'type':'message','id':'message_1','content':[{'type':'output_text','text':'PUBLIC_FIXTURE_OK'}]}),
              frame('response.completed',response={'output':[]})]
    emitted, reason = asyncio.run(inspect(ResponsesHandler(), frames))
    assert reason is None and emitted == b''.join(frames)


@pytest.mark.parametrize('arguments,reason', [('{}',None), ('{"cmd":"AICTRL_\\u0053ECRET_demo"}','guard.secret.detected'), ('{bad','guard.output.invalid_arguments')])
def test_done_only_function_arguments_are_complete_and_checked(arguments, reason):
    frames = [frame('response.created'), frame('response.output_item.done', item={'type':'function_call','id':'tool_1','arguments':arguments}), frame('response.completed')]
    emitted, observed = asyncio.run(inspect(ResponsesHandler(), frames))
    assert observed == reason
    assert emitted == (frames[0] if reason else b''.join(frames))


@pytest.mark.parametrize('parts,reason', [(['ordinary ', 'public text'],None), (['AICTRL_SEC','RET_demo123'],'guard.secret.detected'), (['user@','example.com'],'guard.pii.output_blocked')])
def test_delta_first_native_items_wait_for_identified_done(parts, reason):
    frames = [frame('response.created'),
              *(frame('response.output_text.delta',item_id='message_1',delta=part) for part in parts),
              frame('response.output_item.done', item={'type':'message','id':'message_1','content':[{'type':'output_text','text':'ordinary public text'}]}), frame('response.completed')]
    emitted, observed = asyncio.run(inspect(ResponsesHandler(), frames))
    assert observed == reason
    assert emitted == (frames[0] if reason else b''.join(frames))


def test_interleaved_id_units_retain_order_until_all_close():
    frames = [frame('response.output_item.added',item={'type':'message','id':'message_1','content':[]}),
              frame('response.output_item.added',item={'type':'message','id':'message_2','content':[]}),
              frame('response.output_text.delta',item_id='message_1',delta='one'),
              frame('response.output_text.delta',item_id='message_2',delta='two'),
              frame('response.output_item.done',item={'type':'message','id':'message_1','content':[]}),
              frame('response.output_item.done',item={'type':'message','id':'message_2','content':[]})]
    buffer = ResponsesHandler().new_output_buffer(1048576)
    for chunk in frames[:-1]:
        assert buffer.feed(chunk) == []
    units = buffer.feed(frames[-1])
    assert len(units) == 1 and units[0].raw == b''.join(frames)
    assert buffer.aliases == {} and not buffer.active
    buffer.finish()


def test_ambiguous_unidentified_delta_is_withheld():
    frames = [frame('response.created'),
              frame('response.output_item.added',item={'type':'message','id':'message_1','content':[]}),
              frame('response.output_item.added',item={'type':'message','id':'message_2','content':[]}),
              frame('response.output_text.delta',delta='ambiguous')]
    emitted, reason = asyncio.run(inspect(ResponsesHandler(),frames))
    assert reason == 'guard.output.invalid' and emitted == frames[0]


def test_generic_sse_transport_label_uses_native_json_type():
    frames = responses(['ordinary ', 'public text'])
    generic = [chunk.replace(chunk.split(b'\n',1)[0], b'event: message', 1) for chunk in frames]
    emitted, reason = asyncio.run(inspect(ResponsesHandler(),generic))
    assert reason is None and emitted == b''.join(generic)


def test_done_sentinel_preserved_after_complete_checked_item():
    frames = responses(['ordinary public text']) + [b'data: [DONE]\n\n']
    emitted, reason = asyncio.run(inspect(ResponsesHandler(),frames))
    assert reason is None and emitted == b''.join(frames)


def test_done_sentinel_never_releases_an_incomplete_unit():
    frames = responses(['ordinary public text'])[:-2] + [b'data: [DONE]\n\n']
    emitted, reason = asyncio.run(inspect(ResponsesHandler(),frames))
    assert reason == 'guard.output.incomplete' and emitted == frames[0]


def test_null_initial_placeholders_wait_for_actual_complete_arguments():
    frames = [frame('response.created'),
              frame('response.output_item.added',item={'type':'function_call','id':'tool_1','arguments':None,'content':None}),
              frame('response.function_call_arguments.delta',item_id='tool_1',delta='{"cmd":"pwd"}'),
              frame('response.output_item.done',item={'type':'function_call','id':'tool_1','arguments':'{"cmd":"pwd"}'}),
              frame('response.output_item.added',item={'type':'message','id':'message_1','content':[{'type':'output_text','text':None}]}),
              frame('response.output_text.delta',item_id='message_1',delta='ordinary public text'),
              frame('response.output_item.done',item={'type':'message','id':'message_1','content':[{'type':'output_text','text':'ordinary public text'}]}),
              frame('response.completed')]
    emitted, reason = asyncio.run(inspect(ResponsesHandler(),frames))
    assert reason is None and emitted == b''.join(frames)


def test_transport_label_cannot_hide_a_secret():
    frames = responses(['ordinary public text'])
    frames[1] = frames[1].replace(b'event: response.output_item.added',b'event: AICTRL_SECRET_demo',1)
    emitted, reason = asyncio.run(inspect(ResponsesHandler(),frames))
    assert reason == 'guard.secret.detected' and emitted == frames[0]
