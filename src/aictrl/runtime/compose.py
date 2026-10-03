"""Render the reused topology with host-controlled session configuration."""

import re
from pathlib import Path

import yaml

from aictrl.adapters.base import AgentConfig, RoutingMode
from aictrl.runtime.config import ProjectConfig


def validate_provider_state(volume: str | None, mount: str | None) -> None:
    """Accept a named volume and one provider home from trusted adapter code.

    This is not a host bind/path selector. No traversal, wildcard, nested
    symlink path or Docker mount syntax can pass this boundary.
    """
    if not volume or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}', volume):
        raise ValueError('A safe dedicated provider volume name is required.')
    if not mount or not re.fullmatch(r'/home/dev/\.[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', mount):
        raise ValueError('A dedicated absolute provider home path is required.')


def provider_lease_name(volume: str) -> str:
    # One stable engine reservation for every use of the same named volume,
    # including the existing authentication containers.
    return volume.removesuffix('-state') + '-auth'


def render_compose(project: Path, directory: Path, workspace: Path, settings: ProjectConfig,
                   agent: AgentConfig, session: str, subnet: str, proxy_ip: str,
                   uid: int, gid: int, interactive: bool,
                   test_upstream_network: str | None = None) -> dict:
    validate_provider_state(agent.persistent_state_volume, agent.state_mount)
    topology = yaml.safe_load((project / 'docker/compose.yaml').read_text())
    topology['name'] = 'aictrl-' + session
    labels = {'io.aictrl.session': session, 'io.aictrl.managed': 'true'}
    proxy = topology['services']['proxy']
    proxy['image'] = settings.runtime.proxy_image
    proxy['labels'] = labels
    proxy['volumes'][0]['source'] = str(directory / 'destinations.json')
    proxy['networks']['agent-internal']['ipv4_address'] = proxy_ip
    container = topology['services']['agent']
    container['image'] = agent.image_ref
    container['labels'] = labels
    container['environment'] = dict(agent.environment) | {
        'AICTRL_BOOTSTRAP_MODE': 'runtime', 'AICTRL_PROXY_IP': proxy_ip,
        'AICTRL_UID': str(uid), 'AICTRL_GID': str(gid),
    }
    container['extra_hosts'] = {'proxy': proxy_ip}
    if settings.runtime.routing_mode == RoutingMode.APPLICATION_GATEWAY:
        import ipaddress
        gateway_ip = str(ipaddress.ip_network(subnet)[3])
        container['environment']['AICTRL_GATEWAY_IP'] = gateway_ip
        container['environment']['AICTRL_ROUTING_MODE'] = 'APPLICATION_GATEWAY'
        container['extra_hosts']['gateway'] = gateway_ip
        container['depends_on']['gateway'] = {'condition': 'service_healthy'}
        topology['services']['gateway'] = {
            'profiles': ['runtime'], 'image': settings.gateway.image,
            'user': f'{uid}:{gid}', 'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
            'read_only': True, 'pids_limit': 128, 'mem_limit': '512m', 'cpus': 1,
            'labels': labels, 'tmpfs': ['/tmp:rw,nosuid,nodev,size=32m'],
            'environment': {'AICTRL_SESSION_FILE': '/etc/aictrl/session.json',
                            'AICTRL_POLICY_FILE': '/etc/aictrl/policy.yaml',
                            'AICTRL_EVENTS_DB': '/var/lib/aictrl/events.sqlite3'},
            'volumes': [
                {'type': 'bind', 'source': str(directory / 'session.json'), 'target': '/etc/aictrl/session.json', 'read_only': True, 'bind': {'create_host_path': False}},
                {'type': 'bind', 'source': str(project / 'config/policy.yaml'), 'target': '/etc/aictrl/policy.yaml', 'read_only': True, 'bind': {'create_host_path': False}},
                {'type': 'bind', 'source': str((project / settings.gateway.audit_directory).resolve()), 'target': '/var/lib/aictrl', 'bind': {'create_host_path': False}},
            ],
            'networks': {'agent-internal': {'ipv4_address': gateway_ip}, 'upstream': {}},
            'healthcheck': {'test': ['CMD', 'python', '-c', "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2).status==200"],
                            'interval': '1s', 'timeout': '3s', 'retries': 20},
        }
    container['volumes'][0]['source'] = str(workspace)
    container['cpus'] = settings.limits.cpus
    container['mem_limit'] = str(settings.limits.memory_mb) + 'm'
    container['pids_limit'] = settings.limits.pids
    container['tty'] = interactive
    container['stdin_open'] = True
    topology['networks']['agent-internal']['ipam']['config'] = [{'subnet': subnet}]
    for network in topology['networks'].values():
        network['labels'] = labels
    if test_upstream_network is not None:
        # Deterministic Docker probes attach a synthetic backend to this network.
        topology['networks']['upstream'] = {'external': True, 'name': test_upstream_network}
    container['volumes'][1] = 'provider-state:' + agent.state_mount
    topology['volumes']['provider-state'] = {'external': True, 'name': agent.persistent_state_volume}
    for name in ('proxy-private-ca', 'proxy-public-ca'):
        topology['volumes'][name]['labels'] = labels
    return topology
