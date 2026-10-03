import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request

from aictrl.gateway.anthropic import AnthropicGateway
from aictrl.gateway.session import GatewaySession, load_session
from aictrl.policy.engine import PolicyEngine
from aictrl.policy.loader import load_policy
from aictrl.policy.models import Policy
from aictrl.reporting.store import EventStore


def create_app(session: GatewaySession, policy: Policy, store: EventStore,
               client: httpx.AsyncClient | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        owned = client is None
        upstream = client or httpx.AsyncClient(trust_env=False,
                         timeout=httpx.Timeout(connect=10, read=310, write=30, pool=10),
                         limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))
        app.state.gateway = AnthropicGateway(session, PolicyEngine(policy), store, upstream)
        try:
            yield
        finally:
            if owned:
                await upstream.aclose()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)

    @app.get('/health')
    async def health():
        return {'status': 'ready'}

    @app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'])
    async def native(request: Request, path: str):
        return await app.state.gateway.handle(request)

    return app


def from_environment() -> FastAPI:
    return create_app(load_session(Path(os.environ['AICTRL_SESSION_FILE'])),
                      load_policy(Path(os.environ['AICTRL_POLICY_FILE'])),
                      EventStore(Path(os.environ['AICTRL_EVENTS_DB'])))
