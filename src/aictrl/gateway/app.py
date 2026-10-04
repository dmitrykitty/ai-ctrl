import os
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request

from aictrl.gateway.control import ControlPipeline
from aictrl.gateway.registry import resolve_handler
from aictrl.gateway.session import GatewaySession, load_session
from aictrl.policy.loader import load_policy
from aictrl.policy.models import Policy
from aictrl.reporting.store import EventStore
from aictrl.reporting.sink import EventSink
from pydantic import SecretStr
from starlette.routing import Route
from aictrl.guards.jev import JevSemanticProvider, load_key
from aictrl.guards.semantic import SemanticDecisionProvider
from aictrl.mcp.control import MCPControlService
from aictrl.mcp.backend import MCPBackend
from aictrl.mcp.demo_backend import DemoMCPBackend
from aictrl.mcp.server import MCPIdentityBoundary, create_mcp_server, http_app
from aictrl.governance.budgets import BudgetManager
from aictrl.governance.store import GovernanceStore
from aictrl.governance.reload import ConfigSnapshotManager
from aictrl.guards.threat_feed import ThreatFeed
from aictrl.reporting.service import ReportingStore
from aictrl.reporting.sink import StoreFailure


def create_app(session: GatewaySession, policy: Policy, store: EventSink,
               client: httpx.AsyncClient | None = None, *,
               semantic_provider: SemanticDecisionProvider | None = None,
               semantic_key: SecretStr | None = None, backend: MCPBackend | None = None,
               governance_store: GovernanceStore | None = None, feed: ThreatFeed | None = None,
               policy_path: Path | None = None, feed_path: Path | None = None) -> FastAPI:
    if session.agent_id != session.adapter:
        raise ValueError('Inconsistent trusted gateway agent identity.')
    handler = resolve_handler(session.protocol)
    governance = governance_store or (GovernanceStore(store.path) if isinstance(store, EventStore) else None)
    reporting = ReportingStore(store.path) if isinstance(store, EventStore) else None
    @asynccontextmanager
    async def lifespan(app):
        owned = client is None
        upstream = client or httpx.AsyncClient(trust_env=False,
                         timeout=httpx.Timeout(connect=10, read=310, write=30, pool=10),
                         limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))
        timeout = 10  # upper transport bound; captured guard policy sets the actual deadline
        jev_client = httpx.AsyncClient(trust_env=False, follow_redirects=False,
                                      timeout=httpx.Timeout(connect=timeout, read=timeout, write=timeout, pool=timeout),
                                      transport=httpx.AsyncHTTPTransport(retries=0))
        provider = semantic_provider or JevSemanticProvider(jev_client, semantic_key)
        snapshots = ConfigSnapshotManager(policy, provider, feed=feed, policy_path=policy_path, feed_path=feed_path)
        app.state.snapshots, app.state.governance, app.state.reporting = snapshots, governance, reporting
        current = snapshots.capture()
        budgets = BudgetManager(governance) if governance else None
        app.state.gateway = ControlPipeline(session, current.engine, store, upstream, handler, current.guards,
                                            snapshots=snapshots, governance=budgets, reporting=reporting)
        app.state.mcp = MCPControlService(session, current.engine, current.guards, store, backend or DemoMCPBackend(),
                                         snapshots=snapshots, governance=budgets, reporting=reporting)
        mcp_app = http_app(create_mcp_server(lambda: app.state.mcp))
        app.state.mcp_http_app = mcp_app
        def status_report():
            if reporting is not None:
                try:
                    reporting.status(session.session_id, snapshots.capture(), snapshots.status(),
                                     'explicit-offline-fixture' if semantic_provider else 'configured' if semantic_key else 'unavailable')
                except StoreFailure:
                    logging.getLogger('aictrl.reporting').warning('Control status persistence unavailable for session %s', session.session_id)
        status_report()
        watcher = asyncio.create_task(snapshots.watch(status_report))
        try:
            async with mcp_app.router.lifespan_context(mcp_app):
                yield
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
            await jev_client.aclose()
            if owned:
                await upstream.aclose()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)

    @app.get('/health')
    async def health():
        return {'status': 'ready', **app.state.snapshots.status(),
                'semantic_provider': 'configured' if semantic_key or semantic_provider else 'unavailable; semantic-required operations fail closed'}

    app.router.routes.append(Route('/mcp', endpoint=MCPIdentityBoundary(lambda: app.state.mcp_http_app, lambda: app.state.mcp)))

    @app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'])
    async def native(request: Request, path: str):
        return await app.state.gateway.handle(request)

    return app


def from_environment() -> FastAPI:
    from aictrl.guards.threat_feed import load_feed
    policy_path = Path(os.environ['AICTRL_POLICY_FILE'])
    feed_path = Path(os.environ['AICTRL_THREAT_FEED_FILE'])
    return create_app(load_session(Path(os.environ['AICTRL_SESSION_FILE'])),
                      load_policy(policy_path),
                      EventStore(Path(os.environ['AICTRL_EVENTS_DB'])), semantic_key=load_key(),
                      feed=load_feed(feed_path), policy_path=policy_path, feed_path=feed_path)
