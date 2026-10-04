"""Actual SDK workload for the host-coordinated governance demonstration.

The checkpoint contains a fixed phase only. Host approval verifies the exact
counter-only operation/digest against its own expected request before using CLI.
No policy, arguments, key or internal token is written to the checkpoint.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

CHECKPOINT = Path('/workspace/t07-checkpoint.json')


def phase(name: str) -> None:
    CHECKPOINT.with_suffix('.tmp').write_text(json.dumps({'phase': name}))
    CHECKPOINT.with_suffix('.tmp').replace(CHECKPOINT)


async def wait_health(http, url, **expected):
    for _ in range(100):
        health = (await http.get(url + '/health')).json()
        if all(health.get(key) == value for key, value in expected.items()):
            return health
        await asyncio.sleep(0.1)
    raise RuntimeError('Expected governance configuration did not become active.')


async def demonstrate() -> int:
    checks = {}
    def check(label, passed):
        checks[label] = bool(passed)
        if not passed:
            raise RuntimeError('Governance demo check failed.')
    url = os.environ['AICTRL_GATEWAY_URL']
    async with httpx2.AsyncClient(headers={'X-AICtrl-Session': os.environ['AICTRL_SESSION_TOKEN']}, trust_env=False, timeout=15) as http:
        async with Client(streamable_http_client(url + '/mcp', http_client=http), cache=None) as client:
            tools = {tool.name for tool in (await client.list_tools()).tools}
            check('approval_tool_visible', 'destructive_delete_all' in tools)
            safe = await client.call_tool('safe_lookup', {})
            check('normal_tool_below_budget', not safe.is_error and 'destructive_backend_invocations=0' in str(safe))
            arguments = {'confirmation': 't07-demo'}
            pending = await client.call_tool('destructive_delete_all', arguments)
            check('approval_pending_no_execution', pending.is_error and 'governance.approval.required' in str(pending))
            phase('pending')
            # Host explicitly runs aictrl approvals + approve. This workload can
            # only retry the same protected operation; it cannot grant approval.
            for _ in range(60):
                await asyncio.sleep(0.25)
                approved = await client.call_tool('destructive_delete_all', arguments)
                if not approved.is_error:
                    break
                check('waiting_still_requires_approval', 'governance.approval.required' in str(approved))
            check('approved_exact_call_executes', not approved.is_error)
            replay = await client.call_tool('destructive_delete_all', arguments)
            check('approval_replay_denied', replay.is_error and 'governance.approval.consumed' in str(replay))
            changed = await client.call_tool('destructive_delete_all', {'confirmation': 'changed'})
            check('changed_arguments_require_fresh_approval', changed.is_error and 'governance.approval.required' in str(changed))
            count = await client.call_tool('safe_lookup', {})
            check('destructive_counter_exactly_one', not count.is_error and 'destructive_backend_invocations=1' in str(count))
            phase('approval_complete')
            await wait_health(http, url, active_policy_version='t07-demo-budget')
            denied = await client.call_tool('safe_lookup', {})
            check('small_tool_budget_blocks', denied.is_error and 'governance.budget.tool_calls_exceeded' in str(denied))
            discovery = await client.list_tools()
            check('discovery_not_tool_budget', bool(discovery.tools))
            phase('budget_complete')
            await wait_health(http, url, active_policy_version='t07-demo-block')
            denied = await client.call_tool('safe_lookup', {})
            check('policy_reload_applies', denied.is_error and 'mcp.policy.blocked' in str(denied))
            phase('policy_complete')
            await wait_health(http, url, active_policy_version='t07-demo-feed', active_feed_version='t07-demo-threat')
            denied = await client.call_tool('echo_contact', {'contact': 'AICTRL_GOVERNANCE_FEED_BLOCK'})
            check('feed_reload_blocks_before_backend', denied.is_error and 'guard.threat_feed.detected' in str(denied))
            phase('feed_complete')
            health = await wait_health(http, url, last_policy_reload_status='invalid_candidate', last_feed_reload_status='invalid_candidate')
            check('invalid_reload_retains_policy', health['active_policy_version'] == 't07-demo-feed')
            check('invalid_reload_retains_feed', health['active_feed_version'] == 't07-demo-threat')
            denied = await client.call_tool('echo_contact', {'contact': 'AICTRL_GOVERNANCE_FEED_BLOCK'})
            check('last_good_feed_still_blocks', denied.is_error and 'guard.threat_feed.detected' in str(denied))
            safe = await client.call_tool('safe_lookup', {})
            check('gateway_ready_with_last_good', not safe.is_error)
            phase('invalid_complete')
            await wait_health(http, url, active_policy_version='t07-demo-runaway')
            denied = await client.call_tool('safe_lookup', {})
            check('lifetime_runaway_blocks', denied.is_error and 'governance.runaway.tool_calls_exceeded' in str(denied))
    phase('done')
    for _ in range(100):
        if Path('/workspace/t07-host-completed').is_file():
            break
        await asyncio.sleep(0.05)
    check('host_finished_before_cleanup', Path('/workspace/t07-host-completed').is_file())
    print('AICTRL_T07_GOVERNANCE_CLIENT ' + json.dumps(checks, sort_keys=True), flush=True)
    print('T07 GOVERNANCE DEMO PASS', flush=True)
    return 0


if __name__ == '__main__':
    logging.getLogger('mcp').setLevel(logging.CRITICAL)
    try:
        status = asyncio.run(demonstrate())
    except Exception:
        print('T07 GOVERNANCE DEMO FAIL: protected operation or host coordination unavailable.', flush=True)
        status = 1
    raise SystemExit(status)
