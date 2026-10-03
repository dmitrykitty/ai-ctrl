import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request

from aictrl.gateway.control import ControlPipeline
from aictrl.gateway.registry import resolve_handler
from aictrl.gateway.session import GatewaySession, load_session
from aictrl.policy.engine import PolicyEngine
from aictrl.policy.loader import load_policy
from aictrl.policy.models import Policy
from aictrl.reporting.store import EventStore
from aictrl.reporting.sink import EventSink
from pydantic import SecretStr
from starlette.routing import Route
from aictrl.guards.engine import GuardEngine
from aictrl.guards.jev import JevSemanticProvider, load_key
from aictrl.guards.semantic import SemanticDecisionProvider
from aictrl.mcp.control import MCPControlService
from aictrl.mcp.backend import MCPBackend
from aictrl.mcp.demo_backend import DemoMCPBackend
from aictrl.mcp.server import MCPIdentityBoundary, create_mcp_server, http_app


def create_app(session: GatewaySession, policy: Policy, store: EventSink,
               client: httpx.AsyncClient | None = None, *,
               semantic_provider: SemanticDecisionProvider | None = None,
               semantic_key: SecretStr | None = None, backend: MCPBackend | None = None) -> FastAPI:
    if session.agent_id != session.adapter:
        raise ValueError('Inconsistent trusted gateway agent identity.')
    handler = resolve_handler(session.protocol)
    @asynccontextmanager
    async def lifespan(app):
        owned = client is None
        upstream = client or httpx.AsyncClient(trust_env=False,
                         timeout=httpx.Timeout(connect=10, read=310, write=30, pool=10),
                         limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))
        timeout = policy.guards.semantic.timeout_ms / 1000
        jev_client = httpx.AsyncClient(trust_env=False, follow_redirects=False,
                                      timeout=httpx.Timeout(connect=timeout, read=timeout, write=timeout, pool=timeout),
                                      transport=httpx.AsyncHTTPTransport(retries=0))
        provider = semantic_provider or JevSemanticProvider(jev_client, semantic_key)
        guards = GuardEngine(policy.guards, provider)
        engine = PolicyEngine(policy)
        app.state.gateway = ControlPipeline(session, engine, store, upstream, handler, guards)
        app.state.mcp = MCPControlService(session, engine, guards, store, backend or DemoMCPBackend())
        mcp_app = http_app(create_mcp_server(lambda: app.state.mcp))
        app.state.mcp_http_app = mcp_app
        try:
            async with mcp_app.router.lifespan_context(mcp_app):
                yield
        finally:
            await jev_client.aclose()
            if owned:
                await upstream.aclose()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)

    @app.get('/health')
    async def health():
        return {'status': 'ready', 'semantic_provider': 'configured' if semantic_key or semantic_provider else 'unavailable; semantic-required operations fail closed'}

    app.router.routes.append(Route('/mcp', endpoint=MCPIdentityBoundary(lambda: app.state.mcp_http_app, lambda: app.state.mcp)))

    @app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'])
    async def native(request: Request, path: str):
        return await app.state.gateway.handle(request)

    return app


def from_environment() -> FastAPI:
    return create_app(load_session(Path(os.environ['AICTRL_SESSION_FILE'])),
                      load_policy(Path(os.environ['AICTRL_POLICY_FILE'])),
                      EventStore(Path(os.environ['AICTRL_EVENTS_DB'])), semantic_key=load_key())
