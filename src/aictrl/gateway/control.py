"""Native, fixed-origin forwarding with durable admission before any POST."""

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import Request
from starlette.responses import JSONResponse, StreamingResponse

from aictrl.contracts import ControlRequest, PolicyContext, SecurityEvent, DecisionAction
from aictrl.gateway.headers import HOP_BY_HOP, response_headers
from aictrl.gateway.protocols import NativeProtocolHandler
from aictrl.gateway.session import GatewaySession
from aictrl.policy.engine import PolicyEngine
from aictrl.reporting.sink import EventSink, StoreFailure

MAX_BODY = 16 * 1024 * 1024
logger = logging.getLogger('aictrl.gateway')


class GatewayStreamFailure(RuntimeError):
    pass


class ControlPipeline:
    def __init__(self, session: GatewaySession, engine: PolicyEngine, store: EventSink,
                 client: httpx.AsyncClient, handler: NativeProtocolHandler) -> None:
        self.session, self.engine, self.store, self.client = session, engine, store, client
        self.handler = handler

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
        operation = self.handler.resolve_operation(incoming.method, incoming.url.path)
        control = ControlRequest(session_id=self.session.session_id, channel=self.handler.channel, direction=self.handler.direction,
                                 protocol=self.handler.protocol, inspection_level=self.handler.inspection_level,
                                 target_id=self.handler.target, operation_id=operation or 'unsupported', created_at=datetime.now(timezone.utc))
        prefix = control.channel.value.lower()
        if not self.session.accepts(incoming.headers.getlist('x-aictrl-session')):
            return await self.block(control, prefix + '.invalid_session', 401)
        if operation is None:
            return await self.block(control, prefix + '.policy.blocked')
        context = PolicyContext(session_id=self.session.session_id, agent_id=self.session.agent_id,
                                user_id=self.session.user_id, profile_id=self.session.profile_id,
                                policy_version=self.engine.policy.policy_version)
        try:
            decision = self.engine.decide(context, control)
        except Exception:
            return await self.block(control, prefix + '.policy_error', 503)
        if decision.action != DecisionAction.ALLOW:
            return await self.block(control, decision.reason_code)
        body = bytearray()
        try:
            async for chunk in incoming.stream():
                if len(body) + len(chunk) > MAX_BODY:
                    return await self.block(control, prefix + '.body_too_large', 413)
                body.extend(chunk)
            payload = json.loads(body)
            if not self.handler.validate_payload(payload, operation):
                raise ValueError('Invalid native body')
        except (ValueError, UnicodeError):
            return await self.block(control, prefix + '.invalid_body', 400)
        # T06 deterministic guards and the Jev semantic stage belong here:
        # once for every protocol, before the durable admission and upstream.
        try:
            await self.record(control, DecisionAction.ALLOW, decision.reason_code)
        except StoreFailure:
            return self.error(control, 503, 'AICTRL admission audit unavailable.')
        # Origin and path are trusted constants. The caller's query is data only.
        url = self.handler.build_upstream_url(operation, incoming.scope['query_string'])
        try:
            outbound = self.client.build_request('POST', url, content=bytes(body), headers=self.handler.filter_request_headers(incoming.headers.raw))
            for name in HOP_BY_HOP:
                outbound.headers.pop(name.decode(), None)
            upstream = await self.client.send(outbound, stream=True, follow_redirects=False)
        except httpx.HTTPError:
            await self.final_record(control, prefix + '.upstream_failed')
            return self.error(control, 502, 'AICTRL upstream unavailable.')

        async def relay():
            reason = prefix + '.upstream_failed'
            observer = self.handler.new_stream_observer()
            try:
                async for chunk in upstream.aiter_raw():
                    if observer is not None:
                        observer.observe(chunk)
                    yield chunk
                if upstream.status_code < 400 and (observer is None or observer.completed and not observer.failed):
                    reason = prefix + '.upstream_completed'
            except httpx.HTTPError:
                raise GatewayStreamFailure('AICTRL upstream stream interrupted.') from None
            finally:
                # Native terminal evidence can establish completion before
                # HTTP EOF. Arbitrary early disconnects remain failed.
                if observer is not None and upstream.status_code < 400 and observer.completed and not observer.failed:
                    reason = prefix + '.upstream_completed'
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
