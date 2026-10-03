from datetime import datetime, timezone

import pytest
from pydantic import SecretStr

from aictrl.adapters.base import AgentAdapter, EndpointPurpose
from aictrl.adapters.claude import ClaudeAdapter
from aictrl.adapters.demo import DemoAgentAdapter
from aictrl.contracts import AgentSession


def session(adapter="claude", token=SecretStr("synthetic_internal_token_1234567890")):
    return AgentSession(agent_id=adapter, adapter=adapter, user_id="local", profile_id="default",
                        workspace="/workspace", protocol="ANTHROPIC_MESSAGES", billing_mode="SUBSCRIPTION",
                        started_at=datetime.now(timezone.utc), session_token=token)


def test_claude_subscription_environment_is_safe_and_independent():
    adapter = ClaudeAdapter("aictrl-claude:2.1.285-t01")
    assert isinstance(adapter, AgentAdapter)
    config = adapter.render_config(session())
    assert config.persistent_state_volume == "aictrl-claude-state"
    assert config.state_mount == "/home/dev/.claude"
    assert config.entry_command == ("claude",)
    assert config.environment["ANTHROPIC_BASE_URL"] == "http://gateway:8000/anthropic"
    assert "ANTHROPIC_API_KEY" not in config.environment
    assert "ANTHROPIC_AUTH_TOKEN" not in config.environment
    assert "apiKeyHelper" not in config.environment
    assert "synthetic_internal_token" not in config.model_dump_json()
    assert "synthetic_internal_token" not in repr(config)
    config.environment["HTTPS_PROXY"] = "changed"
    assert adapter.render_config(session()).environment["HTTPS_PROXY"] == "http://proxy:8080"
    assert any(endpoint.purpose == EndpointPurpose.AUTHENTICATION for endpoint in config.required_provider_endpoints)


def test_claude_requires_supervisor_identity():
    adapter = ClaudeAdapter("pinned-image")
    with pytest.raises(ValueError, match="token"):
        adapter.render_config(session(token=None))
    with pytest.raises(ValueError, match="different adapter"):
        adapter.render_config(session(adapter="demo-agent"))


def test_demo_has_no_provider_state_or_external_endpoints():
    adapter = DemoAgentAdapter("prepared-demo-image")
    assert isinstance(adapter, AgentAdapter)
    config = adapter.render_config(session(adapter="demo-agent"))
    assert config.persistent_state_volume is None
    assert config.state_mount is None
    assert config.required_provider_endpoints == ()
