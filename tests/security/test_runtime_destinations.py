import asyncio
import importlib.util
import socket
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('runtime_destinations', Path(__file__).resolve().parents[2] / 'docker/proxy/destinations.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DestinationList = module.DestinationList


def test_denied_hosts_and_ports_never_resolve(monkeypatch):
    destinations = DestinationList([{'host': 'allowed.test', 'port': 443}])
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a: pytest.fail('denied authority attempted DNS'))
    for host, port in [('denied.test', 443), ('allowed.test.evil.test', 443), ('allowed.test', 80), ('127.0.0.1', 443)]:
        with pytest.raises(ValueError, match='denied'):
            asyncio.run(destinations.address(host, port))


@pytest.mark.parametrize('answers', [['127.0.0.1'], ['169.254.169.254'], ['172.20.0.1'], ['1.1.1.1', '127.0.0.1'], []])
def test_dns_rebinding_or_mixed_public_private_answers_fail_closed(monkeypatch, answers):
    destinations = DestinationList([{'host': 'allowed.test', 'port': 443}])
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a: [(2, 1, 6, '', (ip, 443)) for ip in answers])
    with pytest.raises(ValueError, match='Non-public'):
        asyncio.run(destinations.address('allowed.test', 443))


def test_public_resolution_returns_checked_numeric_ip(monkeypatch):
    destinations = DestinationList([{'host': 'allowed.test', 'port': 443}])
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a: [(2, 1, 6, '', ('1.1.1.1', 443))])
    assert asyncio.run(destinations.address('ALLOWED.TEST', 443)) == '1.1.1.1'


@pytest.mark.parametrize('records', [[], [{'host': '*.test', 'port': 443}], [{'host': 'allowed.test', 'port': 443, 'url': 'untrusted'}], [{'host': 'allowed.test', 'port': 443}] * 2, [{'host': 'allowed.test', 'port': True}], [{'host': 'allowed.test', 'port': 443, 'connect_ip': '127.0.0.1'}]])
def test_malformed_or_unsafe_proxy_configuration_fails_closed(records):
    with pytest.raises(ValueError):
        DestinationList(records)


def test_synthetic_upstream_requires_explicit_trusted_pin(monkeypatch):
    destinations = DestinationList([{'host': 'allowed.test', 'port': 8081, 'connect_ip': '172.20.0.10'}])
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a: pytest.fail('pinned synthetic target must not resolve'))
    assert asyncio.run(destinations.address('allowed.test', 8081)) == '172.20.0.10'
