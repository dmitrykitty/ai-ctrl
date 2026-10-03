"""Native, fixed-origin forwarding with durable admission before any POST."""

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import Request
from starlette.responses import JSONResponse, StreamingResponse

from aictrl.contracts import ControlRequest, PolicyContext, SecurityEvent, DecisionAction
from aictrl.gateway.headers import HOP_BY_HOP, request_headers, response_headers
from aictrl.gateway.session import GatewaySession
from aictrl.policy.engine import PolicyEngine
from aictrl.reporting.store import EventStore, StoreFailure

UPSTREAM = 'https://api.anthropic.com'
PATHS = {'/anthropic/v1/messages': 'messages', '/anthropic/v1/messages/count_tokens': 'count_tokens'}
MAX_BODY = 16 * 1024 * 1024
logger = logging.getLogger('aictrl.gateway')


class GatewayStreamFailure(RuntimeError):
    pass


class AnthropicGateway:
    def __init__(self, session: GatewaySession, engine: PolicyEngine, store: EventStore,
                 client: httpx.AsyncClient) -> None:
        self.session, self.engine, self.store, self.client = session, engine, store, client

    def event(self, request: ControlRequest, action: DecisionAction, reason: str) -> SecurityEvent:
        return SecurityEvent(session_id=self.session.session_id, request_id=request.request_id,
                             agent_id=self.session.agent_id, adapter=self.session.adapter,
                             channel=request.channel, direction=request.direction, protocol=request.protocol,
                             inspection_level=request.inspection_level, action=action, reason_code=reason,
                             policy_version=self.engine.policy.policy_version,
                             rule_ids=('operation.' + request.operation_id,), occurred_at=datetime.now(timezone.utc))

    async def record(self, request: ControlRequest, action: DecisionAction, reason: str) -> None:
        await asyncio.to_thread(self.store.append, self.event(request, action, reason))

    @staticmethod
    def error(request: ControlRequest, status: int, message: str):
        kind = 'authentication_error' if status == 401 else 'permission_error' if status == 403 else 'api_error'
        return JSONResponse({'type': 'error', 'error': {'type': kind, 'message': message},
                             'request_id': str(request.request_id)}, status_code=status)

    async def block(self, request: ControlRequest, reason: str, status: int = 403):
        try:
            await self.record(request, DecisionAction.BLOCK, reason)
        except StoreFailure:
            return self.error(request, 503, 'AICTRL admission audit unavailable.')
        return self.error(request, status, 'AICTRL request blocked.')

    async def handle(self, incoming: Request):
        operation = PATHS.get(incoming.url.path, 'unsupported') if incoming.method == 'POST' else 'unsupported'
        control = ControlRequest(session_id=self.session.session_id, channel='LLM', direction='OUTBOUND',
                                 protocol='ANTHROPIC_MESSAGES', inspection_level='STRUCTURED',
                                 target_id='anthropic', operation_id=operation, created_at=datetime.now(timezone.utc))
        if not self.session.accepts(incoming.headers.getlist('x-aictrl-session')):
            return await self.block(control, 'llm.invalid_session', 401)
        context = PolicyContext(session_id=self.session.session_id, agent_id=self.session.agent_id,
                                user_id=self.session.user_id, profile_id=self.session.profile_id,
                                policy_version=self.engine.policy.policy_version)
        try:
            decision = self.engine.decide(context, control)
        except Exception:
            return await self.block(control, 'llm.policy_error', 503)
        if decision.action != DecisionAction.ALLOW:
            return await self.block(control, decision.reason_code)
        body = bytearray()
        try:
            async for chunk in incoming.stream():
                body.extend(chunk)
                if len(body) > MAX_BODY:
                    return await self.block(control, 'llm.body_too_large', 413)
            payload = json.loads(body)
            if not isinstance(payload, dict) or not isinstance(payload.get('messages'), list):
                raise ValueError('Invalid native body')
        except (ValueError, UnicodeError):
            return await self.block(control, 'llm.invalid_body', 400)
        try:
            await self.record(control, DecisionAction.ALLOW, decision.reason_code)
        except StoreFailure:
            return self.error(control, 503, 'AICTRL admission audit unavailable.')
        # Origin and path are trusted constants. The caller's query is data only.
        url = httpx.URL(UPSTREAM + '/v1/messages' + ('/count_tokens' if operation == 'count_tokens' else '')).copy_with(query=incoming.scope['query_string'])
        try:
            outbound = self.client.build_request('POST', url, content=bytes(body), headers=request_headers(incoming.headers.raw))
            for name in HOP_BY_HOP:
                outbound.headers.pop(name.decode(), None)
            upstream = await self.client.send(outbound, stream=True, follow_redirects=False)
        except httpx.HTTPError:
            await self.final_record(control, 'llm.upstream_failed')
            return self.error(control, 502, 'AICTRL upstream unavailable.')

        async def relay():
            reason = 'llm.upstream_failed'
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
                reason = 'llm.upstream_completed' if upstream.status_code < 400 else 'llm.upstream_failed'
            except httpx.HTTPError:
                raise GatewayStreamFailure('AICTRL upstream stream interrupted.') from None
            finally:
                try:
                    await upstream.aclose()
                finally:
                    await asyncio.shield(self.final_record(control, reason))

        response = StreamingResponse(relay(), status_code=upstream.status_code)
        response.raw_headers = response_headers(upstream.headers.raw)
        return response

    async def final_record(self, control: ControlRequest, reason: str) -> None:
        try:
            await self.record(control, DecisionAction.AUDIT, reason)
        except StoreFailure:
            # Already-delivered bytes cannot be recalled. No raw exception/data.
            logger.error('Completion audit unavailable for session %s request %s', self.session.session_id, control.request_id)
