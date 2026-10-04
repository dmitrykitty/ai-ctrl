"""Local read-only dashboard. No Docker, credentials or gateway identity."""

from datetime import datetime, timezone
import ipaddress
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from aictrl.contracts import Channel, DecisionAction
from aictrl.reporting.queries import ReportingQueries
from aictrl.reporting.sink import StoreFailure

View = Literal['overview', 'sessions', 'events', 'policies', 'budgets', 'alerts']
TITLES = {'overview': 'Control overview', 'sessions': 'Agent sessions', 'events': 'Security events',
          'policies': 'Policy & inspection', 'budgets': 'Budget ledger', 'alerts': 'Alerts & response'}
ROOT = Path(__file__).parent


def loopback(host: str) -> str:
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError
    except ValueError:
        raise ValueError('Dashboard bind must be a loopback IP address.') from None
    return host


def create_dashboard(queries: ReportingQueries) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    templates = Environment(loader=FileSystemLoader(ROOT / 'templates'), autoescape=select_autoescape(['html']))
    templates.filters['number'] = lambda value: f'{value:,}' if isinstance(value, int) else f'{value:,.1f}' if isinstance(value, float) else '—'
    app.mount('/assets', StaticFiles(directory=ROOT / 'assets'), name='assets')

    @app.middleware('http')
    async def headers(request: Request, call_next):
        # Protect the local listener from DNS rebinding through a remote Host.
        host = request.url.hostname
        try:
            local = host == 'localhost' or ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = False
        if not local:
            return JSONResponse({'error': 'Local dashboard only.'}, status_code=403)
        response = await call_next(request)
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(RequestValidationError)
    async def validation(request, error):
        return JSONResponse({'error': 'Invalid dashboard filters.'}, status_code=422)

    def data(view: View, session: UUID | None, action, channel, reason, since, until, page):
        for name, value in (('since', since), ('until', until)):
            if value is not None and value.tzinfo is None:
                if name == 'since': since = value.replace(tzinfo=timezone.utc)
                else: until = value.replace(tzinfo=timezone.utc)
        if since and until and since > until:
            raise ValueError('Invalid time range.')
        if view == 'overview':
            result = queries.overview()
        elif view == 'sessions':
            result = {'sessions': queries.sessions(page=page)}
        elif view == 'events':
            result = {'events': queries.events(session=session, action=action, channel=channel, reason=reason, since=since, until=until, page=page)}
        elif view == 'policies':
            result = {}
        elif view == 'budgets':
            result = {'budgets': queries.budgets(session)}
        else:
            result = {'alerts': queries.alerts(session, page=page)}
        result.setdefault('status', queries.status())
        return result

    @app.get('/health')
    def health():
        try:
            status = queries.status()
            return {'status': 'ready', 'audit_store': status['audit_store'], 'frontend': 'local-assets'}
        except (StoreFailure, ValueError):
            return JSONResponse({'status': 'reporting-unavailable'}, status_code=503)

    @app.get('/', response_class=HTMLResponse)
    @app.get('/view/{view}', response_class=HTMLResponse)
    @app.get('/{view}', response_class=HTMLResponse)
    def page(request: Request, view: View = 'overview', session: UUID | None = None,
             action: DecisionAction | None = None, channel: Channel | None = None,
             reason: Annotated[str | None, Query(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$')] = None,
             since: datetime | None = None, until: datetime | None = None,
             page: Annotated[int, Query(ge=1, le=2000)] = 1):
        error = None
        try:
            content = data(view, session, action, channel, reason, since, until, page)
        except (StoreFailure, ValueError):
            content, error = {}, 'Reporting data temporarily unavailable. The page will retry automatically.'
        return HTMLResponse(templates.get_template('dashboard.html').render(view=view, title=TITLES[view], titles=TITLES,
                            data=content, error=error, detail=None), status_code=200)

    @app.get('/sessions/{session}', response_class=HTMLResponse)
    def detail(session: UUID):
        try:
            content = queries.detail(session)
            content['status'] = queries.status(session)
            error = None
        except (StoreFailure, ValueError):
            content, error = {}, 'Reporting data temporarily unavailable. Retry shortly.'
        return HTMLResponse(templates.get_template('dashboard.html').render(view='sessions', title='Session evidence',
                            titles=TITLES, data=content, error=error, detail=str(session)))

    @app.get('/api/session/{session}')
    def detail_api(session: UUID):
        try:
            content = queries.detail(session)
            content['status'] = queries.status(session)
            return content
        except (StoreFailure, ValueError):
            return JSONResponse({'error': 'Reporting data temporarily unavailable.'}, status_code=503)

    @app.get('/api/{view}')
    def api(view: View, session: UUID | None = None, action: DecisionAction | None = None, channel: Channel | None = None,
            reason: Annotated[str | None, Query(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$')] = None,
            since: datetime | None = None, until: datetime | None = None,
            page: Annotated[int, Query(ge=1, le=2000)] = 1):
        try:
            return data(view, session, action, channel, reason, since, until, page)
        except (StoreFailure, ValueError):
            return JSONResponse({'error': 'Reporting data temporarily unavailable.'}, status_code=503)

    return app
