"""Record public image identity without reading runtime/container state."""

import json
import subprocess
import sys
from pathlib import Path

component, reference = sys.argv[1:]
path = Path('docker/images.lock.json')
lock = json.loads(path.read_text())
info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', reference]))[0]
lock[component + '_local_ref'] = reference
lock[component + '_image_id'] = info['Id']
lock[component + '_repo_digests'] = info['RepoDigests']
path.write_text(json.dumps(lock, indent=2) + '\n')
