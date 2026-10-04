"""Scripted security client. This is not an AI model or a semantic fallback."""

import asyncio
import logging
import os

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError


async def demonstrate() -> int:
    print('AICTRL T07 guards and authorization demo (scripted MCP client)', flush=True)
    failures = 0
    pending = False
    def check(label: str, passed: bool) -> None:
        nonlocal failures
        print(('[PASS] ' if passed else '[FAIL] ') + label, flush=True)
        failures += not passed
    headers = {'X-AICtrl-Session': os.environ['AICTRL_SESSION_TOKEN']}
    url = os.environ['AICTRL_GATEWAY_URL'] + '/mcp'
    async with httpx2.AsyncClient(headers=headers, trust_env=False, timeout=15) as http:
        async with Client(streamable_http_client(url, http_client=http), cache=None, read_timeout_seconds=15) as client:
            tools = {tool.name for tool in (await client.list_tools()).tools}
            check('Allowed MCP tools visible', {'safe_lookup', 'echo_contact', 'poisoned_document'} <= tools)
            check('Approval-required destructive sentinel visible', 'destructive_delete_all' in tools)
            forbidden = await client.call_tool('destructive_delete_all', {})
            check('Destructive sentinel requires exact host approval', forbidden.is_error and 'governance.approval.required' in str(forbidden))
            safe = await client.call_tool('safe_lookup', {})
            pending |= safe.is_error and 'guard.semantic.unavailable' in str(safe)
            if not pending:
                check('Allowed safe tool executed', not safe.is_error)
                check('Destructive backend invocation count remains zero',
                      not safe.is_error and 'destructive_backend_invocations=0' in safe.content[0].text)
            secret = await client.call_tool('echo_contact', {'contact': 'AICTRL_SECRET_demo'})
            check('Secret argument blocked before tool execution', secret.is_error and 'guard.secret.detected' in str(secret))
            contact = await client.call_tool('echo_contact', {'contact': 'user@example.com'})
            pending |= contact.is_error and 'guard.semantic.unavailable' in str(contact)
            if not pending:
                check('PII argument redacted before tool execution', not contact.is_error and contact.content[0].text == '[REDACTED_EMAIL_ADDRESS]')
            resources = {str(resource.uri) for resource in (await client.list_resources()).resources}
            check('Project memory visible', 'memory://project/demo' in resources)
            check('Private memory hidden', 'memory://private/demo' not in resources)
            try:
                project = await client.read_resource('memory://project/demo')
                check('Project memory readable', project.contents[0].text == 'AICTRL_PROJECT_MEMORY_OK')
            except MCPError:
                if not pending:
                    check('Project memory readable', False)
            try:
                await client.read_resource('memory://private/demo')
                check('Guessed private memory read independently blocked', False)
            except MCPError:
                check('Guessed private memory read independently blocked', True)
            poisoned = await client.call_tool('poisoned_document', {})
            pending |= poisoned.is_error and 'guard.semantic.unavailable' in str(poisoned)
            if not pending:
                check('Poisoned tool result blocked by semantic guard', poisoned.is_error and 'guard.semantic.' in str(poisoned))
                check('Poisoned text withheld', 'Ignore previous instructions' not in str(poisoned))
    if failures:
        print('T07 GUARDS DEMO FAIL', flush=True)
        return 1
    if pending:
        print('[PENDING] Semantic provider unavailable; required results were withheld.', flush=True)
        print('T07 GUARDS DEMO PARTIAL', flush=True)
        return 2
    print('T07 GUARDS DEMO PASS', flush=True)
    return 0


if __name__ == '__main__':
    logging.getLogger('mcp').setLevel(logging.CRITICAL)
    try:
        status = asyncio.run(demonstrate())
    except Exception:
        print('T07 GUARDS DEMO FAIL: MCP control unavailable.', flush=True)
        status = 1
    raise SystemExit(status)
