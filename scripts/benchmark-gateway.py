"""Local HTTP benchmark. No provider requests, credentials, models or judges.

The test-only transport redirects a code-asserted native origin to loopback.
Production routing has no such selector. SQLite admission remains WAL/FULL.
"""

import argparse
import asyncio
import json
import math
import os
import platform
import secrets
import socket
import sys
import tempfile
from collections import Counter
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter_ns
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI, Request
from starlette.responses import StreamingResponse

from aictrl.contracts import ControlRequest, PolicyContext, SecurityEvent
from aictrl.gateway.app import create_app
from aictrl.gateway.session import GatewaySession
from aictrl.policy.engine import PolicyEngine
from aictrl.policy.models import AdmissionRule, AgentPolicy, Policy
from aictrl.reporting.store import EventStore
from aictrl.governance.store import GovernanceStore
from aictrl.policy.models import GovernanceSettings, RunawaySettings
from aictrl.runtime.workspace import PROJECT_ROOT

BODY = b'{"model":"local-synthetic","messages":[{"role":"user","content":"public benchmark"}],"stream":true}'
FRAMES = (b'event: message_start\ndata: {"type":"message_start"}\n\n',
          b'event: message_delta\ndata: {"type":"message_delta","delta":{"text":"LOCAL_OK"}}\n\n',
          b'event: message_stop\ndata: {"type":"message_stop"}\n\n')


def percentiles(samples_ns: list[int]) -> dict[str, float]:
    """Nearest rank over all completed attempts; high-resolution input clock."""
    ordered = sorted(samples_ns)
    return {f'p{p}': round(ordered[max(0, math.ceil(len(ordered) * p / 100) - 1)] / 1_000_000, 6)
            for p in (50, 95, 99)} if ordered else {}


def benchmark_policy() -> Policy:
    rule = AdmissionRule(id='benchmark.messages', channel='LLM', direction='OUTBOUND', protocol='ANTHROPIC_MESSAGES',
                         target='anthropic', operations=('messages',), action='ALLOW')
    return Policy(schema_version=4, policy_version='local-benchmark', default_action='BLOCK',
                  agents={'benchmark-agent': AgentPolicy(enabled=True, rules=(rule,))},
                  governance=GovernanceSettings(runaway=RunawaySettings(max_agent_steps=100000, max_tool_calls=100000)))


def microbenchmarks(root: Path, policy_iterations: int, sqlite_iterations: int) -> dict:
    sid = uuid4()
    policy = benchmark_policy()
    engine = PolicyEngine(policy)
    context = PolicyContext(session_id=sid, agent_id='benchmark-agent', user_id='local', profile_id='local',
                            policy_version=policy.policy_version)
    request = ControlRequest(session_id=sid, channel='LLM', direction='OUTBOUND', protocol='ANTHROPIC_MESSAGES',
                             inspection_level='STRUCTURED', target_id='anthropic', operation_id='messages',
                             created_at=datetime.now(timezone.utc))
    policy_times = []
    for _ in range(policy_iterations):
        start = perf_counter_ns()
        decision = engine.decide(context, request)
        policy_times.append(perf_counter_ns() - start)
        assert decision.action == 'ALLOW'
    store = EventStore(root / 'micro.sqlite3')
    sqlite_times = []
    for _ in range(sqlite_iterations):
        event = SecurityEvent(session_id=sid, request_id=request.request_id, agent_id='benchmark-agent', adapter='benchmark-agent',
                              channel=request.channel, direction=request.direction, protocol=request.protocol,
                              inspection_level=request.inspection_level, action='ALLOW', reason_code='llm.policy.allowed',
                              policy_version=policy.policy_version, occurred_at=datetime.now(timezone.utc))
        start = perf_counter_ns()
        store.append(event)
        sqlite_times.append(perf_counter_ns() - start)
    assert len(EventStore(store.path).events(sid)) == sqlite_iterations
    return {'policy': {'iterations': policy_iterations, 'latency_ms': percentiles(policy_times)},
            'sqlite_append': {'iterations': sqlite_iterations, 'latency_ms': percentiles(sqlite_times)}}


class TimedSink:
    """Measurement wrapper; returning still means the underlying commit ended."""
    def __init__(self, store: EventStore):
        self.store = store
        self.samples: list[int] = []

    def append(self, event: SecurityEvent) -> None:
        start = perf_counter_ns()
        self.store.append(event)
        self.samples.append(perf_counter_ns() - start)


class LoopbackTransport(httpx.AsyncBaseTransport):
    """Benchmark-only injection, after asserting the production fixed URL."""
    def __init__(self, port: int):
        self.port = port
        self.transport = httpx.AsyncHTTPTransport(retries=0, limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        assert request.url.scheme == 'https' and request.url.host == 'api.anthropic.com'
        assert request.url.path == '/v1/messages' and 'x-aictrl-session' not in request.headers
        url = request.url.copy_with(scheme='http', host='127.0.0.1', port=self.port)
        return await self.transport.handle_async_request(httpx.Request(request.method, url, headers=request.headers, content=request.content))

    async def aclose(self) -> None:
        await self.transport.aclose()


class LocalServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self):
        # asyncio.run owns interruption; both local servers clean up together.
        yield


@asynccontextmanager
async def serve_local(app: FastAPI):
    # asyncio's TCP_NODELAY setup checks sock.proto == IPPROTO_TCP. A socket
    # created with proto=0 skips it and injects ~40 ms delayed ACK into SSE.
    # Match ordinary uvicorn listener creation instead of measuring that bug.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    sock.bind(('127.0.0.1', 0))
    sock.setblocking(False)
    port = sock.getsockname()[1]
    server = LocalServer(uvicorn.Config(app, host='127.0.0.1', port=port, access_log=False, log_level='critical',
                                        loop='asyncio', http='h11', lifespan='on'))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        for _ in range(1000):
            if server.started:
                break
            if task.done():
                await task
                raise RuntimeError('Local benchmark server did not start.')
            await asyncio.sleep(.005)
        if not server.started:
            raise RuntimeError('Local benchmark startup timed out.')
        yield port
    finally:
        server.should_exit = True
        await task
        sock.close()


async def measure(client: httpx.AsyncClient, url: str, requests: int, concurrency: int, headers: dict) -> dict:
    next_index = iter(range(requests))
    latencies, failures = [], Counter()
    successful = 0

    async def worker():
        nonlocal successful
        for _ in next_index:
            start = perf_counter_ns()
            try:
                response = await client.post(url, content=BODY, headers=headers)
                if response.status_code == 200 and response.content == b''.join(FRAMES):
                    successful += 1
                else:
                    failures['http_' + str(response.status_code) if response.status_code != 200 else 'unexpected_bytes'] += 1
            except httpx.HTTPError as error:
                failures[type(error).__name__] += 1
            latencies.append(perf_counter_ns() - start)

    start = perf_counter_ns()
    await asyncio.gather(*(worker() for _ in range(concurrency)))
    elapsed = (perf_counter_ns() - start) / 1_000_000_000
    return {'requests': requests, 'concurrency': concurrency, 'successful': successful, 'failed': sum(failures.values()),
            'failure_categories': dict(failures), 'seconds': round(elapsed, 6),
            'requests_per_second': round(successful / elapsed, 3), 'latency_ms': percentiles(latencies)}


async def http_benchmark(root: Path, requests: int, concurrencies: tuple[int, ...]) -> dict:
    synthetic = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    hits = 0

    @synthetic.post('/v1/messages')
    async def messages(request: Request):
        nonlocal hits
        assert await request.body() == BODY
        hits += 1
        async def stream():
            for frame in FRAMES:
                yield frame
                await asyncio.sleep(0)
        return StreamingResponse(stream(), media_type='text/event-stream')

    store = EventStore(root / 'gateway.sqlite3')
    timed_sink = TimedSink(store)
    token = secrets.token_urlsafe(48)
    session = GatewaySession(session_id=uuid4(), agent_id='benchmark-agent', adapter='benchmark-agent', protocol='ANTHROPIC_MESSAGES',
                             user_id='local', profile_id='local', expires_at=datetime.now(timezone.utc) + timedelta(hours=1), session_token=token)
    results = {'direct': [], 'gateway': []}
    async with serve_local(synthetic) as backend_port:
        async with httpx.AsyncClient(transport=LoopbackTransport(backend_port), trust_env=False,
                                    timeout=httpx.Timeout(connect=10, read=310, write=30, pool=10)) as upstream:
            gateway = create_app(session, benchmark_policy(), timed_sink, upstream, governance_store=GovernanceStore(store.path))
            async with serve_local(gateway) as gateway_port:
                for concurrency in concurrencies:
                    for kind, port, path, headers in (
                        ('direct', backend_port, '/v1/messages', {}),
                        ('gateway', gateway_port, '/anthropic/v1/messages', {'X-AICtrl-Session': token}),
                    ):
                        # Each independent load cohort starts with its own pool;
                        # idle sockets from a different phase cannot skew it.
                        async with httpx.AsyncClient(trust_env=False, timeout=30,
                                                    limits=httpx.Limits(max_connections=100, max_keepalive_connections=100)) as downstream:
                            url = f'http://127.0.0.1:{port}' + path
                            warm = await measure(downstream, url, 3, 1, headers)
                            if warm['failed']:
                                raise RuntimeError('Local benchmark warm-up failed.')
                            timed_sink.samples.clear()
                            print(f'Local benchmark: {kind}, concurrency={concurrency}, requests={requests}', file=sys.stderr, flush=True)
                            result = await measure(downstream, url, requests, concurrency, headers)
                            if kind == 'gateway':
                                result['durable_append_latency_ms'] = percentiles(timed_sink.samples)
                            results[kind].append(result)
    events = EventStore(store.path).events(session.session_id)
    admissions = {event.request_id for event in events if event.action == 'ALLOW'}
    completions = {event.request_id for event in events if event.reason_code == 'llm.upstream_completed'}
    expected = sum(row['successful'] + 3 for row in results['gateway'])
    results['verification'] = {'expected_gateway_pairs': expected, 'admissions': len(admissions), 'completions': len(completions),
                               'paired': admissions == completions and len(admissions) == expected,
                               'synthetic_hits': hits, 'internal_token_absent_from_db': token.encode() not in store.path.read_bytes()}
    return results


def environment(root: Path) -> dict:
    cpu = next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                if line.startswith('model name')), platform.processor())
    return {'date_utc': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(), 'os': platform.platform(),
            'cpu': cpu, 'logical_cpus': os.cpu_count(), 'sqlite_directory': str(root.parent),
            'transport': 'loopback HTTP, asyncio/h11, same Python process, no TLS/provider delay',
            'gateway_upstream_pool': '20 connections / 10 keepalive; production limits',
            'durability': 'SQLite WAL, synchronous FULL; two commits per successful request',
            'percentiles': 'nearest rank, all completed attempts; perf_counter_ns', 'warmup_requests_per_path_per_concurrency': 3}


async def run_benchmark(root: Path, requests: int = 500, concurrencies: tuple[int, ...] = (1, 10, 50),
                        policy_iterations: int = 100_000, sqlite_iterations: int = 300) -> dict:
    return {'scope': 'local synthetic application-layer overhead; not provider/cloud/enterprise latency',
            'environment': environment(root), 'microbenchmarks': microbenchmarks(root, policy_iterations, sqlite_iterations),
            'http': await http_benchmark(root, requests, concurrencies)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requests', type=int, default=500)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.requests < 50:
        parser.error('--requests must be at least 50 for the concurrency-50 sample')
    directory = PROJECT_ROOT / '.aictrl/benchmarks'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix='gateway-', dir=directory) as temporary:
        result = asyncio.run(run_benchmark(Path(temporary), requests=args.requests))
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output is not None:
        args.output.write_text(rendered + '\n')
    return 0 if result['http']['verification']['paired'] and all(not row['failed'] for kind in ('direct', 'gateway')
                                                                  for row in result['http'][kind]) else 1


if __name__ == '__main__':
    raise SystemExit(main())
