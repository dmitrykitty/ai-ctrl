#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
docker build --tag aictrl-proxy:mitm-t02 docker/proxy
python3 - <<'PY'
import json
import subprocess
from pathlib import Path
path = Path('docker/images.lock.json')
lock = json.loads(path.read_text())
info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', 'aictrl-proxy:mitm-t02']))[0]
lock['mitmproxy_base_image'] = 'mitmproxy/mitmproxy@sha256:00b77b5d8804c8ad18cb6caefbf9d5849e895e8986c5ce011f4ae30f4385962f'
lock['mitmproxy_version'] = subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'mitmdump', 'aictrl-proxy:mitm-t02', '--version'], text=True).splitlines()[0]
lock['proxy_local_ref'] = 'aictrl-proxy:mitm-t02'
lock['proxy_image_id'] = info['Id']
lock['proxy_repo_digests'] = info['RepoDigests']
path.write_text(json.dumps(lock, indent=2) + '\n')
PY
