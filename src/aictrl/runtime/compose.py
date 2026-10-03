"""Render the reused topology with host-controlled session configuration."""

from pathlib import Path

import yaml

from aictrl.adapters.base import AgentConfig
from aictrl.runtime.config import ProjectConfig


def render_compose(project: Path, directory: Path, workspace: Path, settings: ProjectConfig,
                   agent: AgentConfig, session: str, subnet: str, proxy_ip: str,
                   uid: int, gid: int, interactive: bool,
                   test_upstream_network: str | None = None) -> dict:
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
    topology['volumes']['claude-state']['name'] = agent.persistent_state_volume
    for name in ('proxy-private-ca', 'proxy-public-ca'):
        topology['volumes'][name]['labels'] = labels
    return topology
