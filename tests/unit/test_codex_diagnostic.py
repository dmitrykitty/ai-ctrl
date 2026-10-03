import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location('codex_live_probe',Path(__file__).parents[1]/'fixtures/codex_live_probe.py')
probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)


def test_native_failure_reports_whitelisted_classification_without_private_lines():
    result = probe.native_evidence(1,'private response','ERROR: unexpected status 401 Unauthorized; invalid_api_key. Bearer synthetic-private-token; private prompt')
    assert result['http_statuses'] == [401] and result['invalid_api_key']
    assert 'synthetic-private-token' not in str(result) and 'private prompt' not in str(result) and 'private response' not in str(result)


def test_scope_failure_is_safe_and_success_requires_exact_response():
    result = probe.native_evidence(1,'','HTTP/1.1 403 Forbidden: missing scopes model.request; synthetic-private-body')
    assert result['missing_model_request_scope'] and result['http_statuses'] == [403]
    assert 'synthetic-private-body' not in str(result)
    assert probe.native_evidence(0,'AICTRL_CODEX_OK\n','')['exact_response']
    assert not probe.native_evidence(0,'prefix AICTRL_CODEX_OK','')['exact_response']
