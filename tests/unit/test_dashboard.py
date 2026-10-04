"""Read-only dashboard routes, accessibility, privacy and failure behavior."""

from html.parser import HTMLParser
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from aictrl.dashboard.app import create_dashboard, loopback
from test_reporting import environment, event, record


class Structure(HTMLParser):
    def __init__(self):super().__init__();self.tags=[]
    def handle_starttag(self,tag,attributes):self.tags.append((tag,dict(attributes)))


@pytest.mark.parametrize('view',['overview','sessions','events','policies','budgets','alerts'])
def test_pages_empty_states_accessibility_and_local_assets(tmp_path,view):
    store,queries,clock=environment(tmp_path)
    with TestClient(create_dashboard(queries),base_url='http://127.0.0.1') as client:
        response=client.get('/' if view=='overview' else '/'+view)
        assert response.status_code==200
        parsed=Structure();parsed.feed(response.text)
        assert sum(tag=='h1' for tag,_ in parsed.tags)==1
        assert any(tag=='nav' and attrs.get('aria-label')=='Primary navigation' for tag,attrs in parsed.tags)
        ids={attrs.get('id') for tag,attrs in parsed.tags if tag in ('input','select')}
        labels={attrs.get('for') for tag,attrs in parsed.tags if tag=='label'}
        assert ids<=labels
        assert 'https://' not in response.text and 'http://' not in response.text
        assert client.get('/assets/dashboard.css').status_code==200
        assert client.get('/assets/dashboard.js').status_code==200
        assert client.get('/api/'+view).status_code==200
        assert client.get('/health').json()['status']=='ready'


def test_representative_data_selected_fields_and_filters(tmp_path):
    store,queries,clock=environment(tmp_path);sid=uuid4();record(store,event(clock,sid))
    with TestClient(create_dashboard(queries),base_url='http://127.0.0.1') as client:
        for path in ('/','/sessions','/events','/policies','/budgets','/alerts','/sessions/'+str(sid)):
            assert client.get(path).status_code==200
        data=client.get('/api/events',params={'action':'BLOCK','channel':'MCP','session':str(sid)}).json()
        assert data['events']['total']==1
        serialized=json.dumps(data)
        for forbidden in ('event_json','session_token','AICTRL_JEV_API_KEY','workspace','raw','request_digest'):
            assert forbidden not in serialized
        for params in ({'page':2001},{'page':0},{'action':'<script>PRIVATE_MARKER</script>'},{'channel':'secret'},{'session':'not-a-uuid'},{'reason':"' OR 1=1 --"}):
            response=client.get('/api/events',params=params)
            assert response.status_code==422 and 'PRIVATE_MARKER' not in response.text
        assert client.post('/api/events').status_code==405
        assert client.get('/',headers={'Host':'external.example'}).status_code==403


def test_dynamic_html_is_escaped_and_malformed_rows_show_safe_error(tmp_path):
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from aictrl.dashboard.app import ROOT
    store,queries,clock=environment(tmp_path)
    templates=Environment(loader=FileSystemLoader(ROOT/'templates'),autoescape=select_autoescape(['html']))
    templates.filters['number']=lambda value: f'{value:,}' if isinstance(value,(int,float)) else value
    rendered=templates.get_template('dashboard.html').render(
        view='overview',title='<script>MARKER</script>',titles={'overview':'Overview'},data={},error='Unavailable',detail=None)
    assert '&lt;script&gt;MARKER&lt;/script&gt;' in rendered and '<script>MARKER' not in rendered
    store.path.unlink()
    with TestClient(create_dashboard(queries),base_url='http://127.0.0.1') as client:
        assert 'temporarily unavailable' in client.get('/').text
        assert client.get('/api/overview').status_code==503
        assert client.get('/health').status_code==503


@pytest.mark.parametrize('host',['0.0.0.0','192.168.1.1','example.com',''])
def test_nonloopback_bind_refused(host):
    with pytest.raises(ValueError):loopback(host)
