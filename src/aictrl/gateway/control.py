"""Native, fixed-origin forwarding with durable admission before any POST."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from time import monotonic

import httpx
from fastapi import Request
from starlette.responses import JSONResponse, StreamingResponse

from aictrl.contracts import ControlRequest, PolicyContext, SecurityEvent, DecisionAction
from aictrl.gateway.headers import HOP_BY_HOP, response_headers
from aictrl.gateway.protocols import NativeProtocolHandler
from aictrl.gateway.session import GatewaySession
from aictrl.policy.engine import PolicyEngine
from aictrl.reporting.sink import EventSink, StoreFailure
from aictrl.gateway.inspection import output_segments, strict_json
from aictrl.gateway.output import OutputBlocked
from aictrl.gateway.output_diagnostics import UNPARSED, rejected_frame, transport_context
from aictrl.guards.engine import GuardEngine
from aictrl.guards.models import apply_replacements
from aictrl.gateway.audit import EventRecorder

MAX_BODY = 16 * 1024 * 1024
logger = logging.getLogger('aictrl.gateway')


class GatewayStreamFailure(RuntimeError):
    pass


class ControlPipeline:
    def __init__(self, session: GatewaySession, engine: PolicyEngine, store: EventSink,
                 client: httpx.AsyncClient, handler: NativeProtocolHandler, guards: GuardEngine | None = None) -> None:
        self.session, self.engine, self.store, self.client = session, engine, store, client
        self.handler = handler
        self.guards = guards or GuardEngine(engine.policy.guards)
        self.audit = EventRecorder(session, engine.policy.policy_version, store)

    def event(self, request: ControlRequest, action: DecisionAction, reason: str,
              identifiers: tuple[str, ...] = ()) -> SecurityEvent:
        return self.audit.event(request, action, reason, identifiers)

    async def record(self, request: ControlRequest, action: DecisionAction, reason: str,
                     identifiers: tuple[str, ...] = ()) -> None:
        await self.audit.record(request, action, reason, identifiers)

    @staticmethod
    def error(request: ControlRequest, status: int, message: str):
        kind = 'authentication_error' if status == 401 else 'permission_error' if status == 403 else 'api_error'
        return JSONResponse({'type': 'error', 'error': {'type': kind, 'message': message},
                             'request_id': str(request.request_id)}, status_code=status)

    async def block(self, request: ControlRequest, reason: str, status: int = 403,
                    identifiers: tuple[str, ...] = ()):
        try:
            await self.record(request, DecisionAction.BLOCK, reason, identifiers)
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
            payload = strict_json(body)
            if not self.handler.validate_payload(payload, operation):
                raise ValueError('Invalid native body')
            inspection = self.handler.extract_inspection(payload)
        except (ValueError, UnicodeError, RecursionError, TypeError):
            return await self.block(control, prefix + '.invalid_body', 400)
        guarded = await self.guards.inspect_input(inspection)
        decision = decision.model_copy(update={'guards': guarded.results})
        if guarded.action == DecisionAction.BLOCK:
            return await self.block(control, guarded.reason_code, identifiers=guarded.identifiers)
        try:
            if guarded.action == DecisionAction.REDACT:
                apply_replacements(payload, guarded.replacements)
                body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
                await self.record(control, DecisionAction.REDACT, 'guard.pii.redacted', guarded.identifiers)
            # T07 budget reservation belongs here, before durable admission.
            await self.record(control, DecisionAction.ALLOW, decision.reason_code)
        except StoreFailure:
            return self.error(control, 503, 'AICTRL admission audit unavailable.')
        # Origin and path are trusted constants. The caller's query is data only.
        url = self.handler.build_upstream_url(operation, incoming.scope['query_string'])
        try:
            outbound = self.client.build_request('POST', url, content=bytes(body), headers=self.handler.filter_request_headers(incoming.headers.raw))
            # Inspection consumes original UTF-8 protocol bytes. Never pass an
            # opaque compressed stream through as inspected output.
            outbound.headers['accept-encoding'] = 'identity'
            for name in HOP_BY_HOP:
                outbound.headers.pop(name.decode(), None)
            upstream = await self.client.send(outbound, stream=True, follow_redirects=False)
        except httpx.HTTPError:
            await self.final_record(control, prefix + '.upstream_failed')
            return self.error(control, 502, 'AICTRL upstream unavailable.')

        async def relay():
            reason = prefix + '.upstream_failed'
            observer = self.handler.new_stream_observer() if upstream.headers.get('content-type', '').split(';', 1)[0].lower() == 'text/event-stream' else None
            output_blocked = False
            transport_failed = False
            try:
                if upstream.headers.get('content-encoding', 'identity').lower() != 'identity':
                    raise OutputBlocked('guard.output.encoding')
                async for chunk in self.inspect_stream(upstream):
                    if observer is not None:
                        observer.observe(chunk)
                    yield chunk
                if upstream.status_code < 400 and (observer is None or observer.completed and not observer.failed):
                    reason = prefix + '.upstream_completed'
            except OutputBlocked as error:
                output_blocked = True
                reason = prefix + '.output_blocked'
                # Every blocking path has transport context, including failures
                # before a frame exists or outside the SSE branch. Fixed
                # vocabulary/types/counts only; no exception or header values.
                logger.warning('AICTRL_OUTPUT_STRUCTURE %s', json.dumps({
                    'session_id': str(control.session_id), 'request_id': str(control.request_id),
                    'schema': 1, 'stage': 'output.check',
                    'transport': transport_context(upstream.headers, upstream.status_code),
                    **(error.diagnostic or {}),
                }, sort_keys=True, separators=(',', ':')))
                try:
                    await self.record(control, DecisionAction.BLOCK, error.reason, error.identifiers)
                except StoreFailure:
                    logger.error('Output audit unavailable for session %s request %s', self.session.session_id, control.request_id)
            except httpx.HTTPError:
                transport_failed = True
                raise GatewayStreamFailure('AICTRL upstream stream interrupted.') from None
            finally:
                # Native terminal evidence can establish completion before
                # HTTP EOF. Arbitrary early disconnects remain failed.
                if not output_blocked and not transport_failed and observer is not None and upstream.status_code < 400 and observer.completed and not observer.failed:
                    reason = prefix + '.upstream_completed'
                try:
                    await upstream.aclose()
                finally:
                    await asyncio.shield(self.final_record(control, reason))

        response = StreamingResponse(relay(), status_code=upstream.status_code)
        response.raw_headers = [(key, value) for key, value in response_headers(upstream.headers.raw)
                                if key.lower() != b'content-length']
        return response

    async def inspect_stream(self, upstream: httpx.Response):
        settings = self.guards.settings.output
        if upstream.headers.get('content-type', '').split(';', 1)[0].lower() == 'text/event-stream':
            buffer = self.handler.new_output_buffer(settings.max_bytes)
            iterator = upstream.aiter_raw().__aiter__()
            while True:
                remaining = settings.timeout_ms / 1000
                if buffer.started is not None:
                    remaining -= monotonic() - buffer.started
                if remaining <= 0:
                    raise OutputBlocked('guard.output.timeout')
                try:
                    async with asyncio.timeout(remaining):
                        chunk = await anext(iterator)
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    raise OutputBlocked('guard.output.timeout') from None
                for unit in buffer.feed(chunk):
                    guarded = await self.guards.inspect_output(unit.segments)
                    if guarded.action == DecisionAction.BLOCK:
                        raise OutputBlocked(guarded.reason_code, guarded.identifiers)
                    yield unit.raw
            buffer.finish()
        else:
            body = bytearray()
            payload = UNPARSED
            stage = 'body.read'
            try:
                async with asyncio.timeout(settings.timeout_ms / 1000):
                    async for chunk in upstream.aiter_raw():
                        if len(body) + len(chunk) > settings.max_bytes:
                            raise OutputBlocked('guard.output.too_large')
                        body.extend(chunk)
                try:
                    stage = 'json.decode'
                    payload = strict_json(body)
                except ValueError as error:
                    if upstream.status_code < 400:
                        raise OutputBlocked('guard.output.invalid', diagnostic=rejected_frame(
                            payload=payload, payload_bytes=len(body), label=None, stage=stage,
                            error=error, active_units=0)) from None
                    stage = 'body.text_decode'
                    payload = body.decode('utf-8')
                stage = 'body.guard'
                guarded = await self.guards.inspect_output(output_segments(payload))
                if guarded.action == DecisionAction.BLOCK:
                    raise OutputBlocked(guarded.reason_code, guarded.identifiers)
                yield bytes(body)
            except TimeoutError:
                raise OutputBlocked('guard.output.timeout') from None
            except (ValueError, UnicodeError, RecursionError) as error:
                raise OutputBlocked(diagnostic=rejected_frame(
                    payload=payload, payload_bytes=len(body), label=None, stage=stage,
                    error=error, active_units=0)) from None

    async def final_record(self, control: ControlRequest, reason: str) -> None:
        try:
            await self.record(control, DecisionAction.AUDIT, reason)
        except StoreFailure:
            # Already-delivered bytes cannot be recalled. No raw exception/data.
            logger.error('Completion audit unavailable for session %s request %s', self.session.session_id, control.request_id)
