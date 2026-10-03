"""Synthetic native Responses with incremental SSE and tool-result follow-up."""
import json
import time
from http.server import ThreadingHTTPServer

from runtime_target import Handler, counts


class ResponsesHandler(Handler):
    def do_POST(self):
        if self.path.split('?', 1)[0] != '/backend-api/codex/responses':
            self.send_error(404)
            return
        raw = self.rfile.read(int(self.headers['Content-Length']))
        body = json.loads(raw)
        assert self.headers.get('X-AICtrl-Session') is None
        assert isinstance(body['input'], (list, str))
        counts['responses'] += 1
        followup = isinstance(body['input'], list) and any(item.get('type') == 'function_call_output' for item in body['input'])
        if followup:
            counts['tool_followup'] += 1
        # Caller selects only synthetic fixture behavior, never a provider URL.
        tool = body.get('metadata', {}).get('synthetic_tool') and not followup
        identifier = 'resp_synthetic_' + str(counts['responses'])
        if tool:
            item = {'id':'fc_synthetic', 'type':'function_call', 'name':'exec_command',
                    'call_id':'call_synthetic', 'arguments':'{"cmd":"printf AICTRL_SYNTHETIC_TOOL_OK","max_output_tokens":50}'}
        else:
            item = {'id':'msg_synthetic', 'type':'message', 'role':'assistant', 'status':'completed',
                    'content':[{'type':'output_text','text':'AICTRL_SYNTHETIC_CODEX_OK','annotations':[]}]}
        response = {'id':identifier,'object':'response','created_at':0,'model':body.get('model','gpt-6-sol'),
                    'status':'completed','output':[item],'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}
        events = [{'type':'response.created','response':dict(response,status='in_progress',output=[])},
                  {'type':'response.output_item.added','output_index':0,'item':item},
                  {'type':'response.output_item.done','output_index':0,'item':item},
                  {'type':'response.completed','response':response}]
        self.send_response(200)
        self.send_header('Content-Type','text/event-stream')
        self.send_header('Connection','close')
        self.end_headers()
        for event in events:
            data = ('event: '+event['type']+'\ndata: '+json.dumps(event)+'\n\n').encode()
            self.wfile.write(data)
            self.wfile.flush()
            time.sleep(.04)
        self.close_connection = True


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0',8081),ResponsesHandler).serve_forever()
