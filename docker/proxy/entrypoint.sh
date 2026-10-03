#!/usr/bin/env bash
# Adapted from agent-sandbox images/proxy/entrypoint.sh (MIT, Matt Olson 2026).
set -euo pipefail
umask 077
test -r "${AICTRL_DESTINATIONS_FILE:?Runtime destination list is required}"
python - <<'PY'
from pathlib import Path
from mitmproxy.certs import CertStore
private = Path('/home/mitmproxy/.mitmproxy')
CertStore.from_store(private, 'mitmproxy', 2048)
public = (private / 'mitmproxy-ca-cert.pem').read_bytes()
if b'PRIVATE KEY' in public or b'BEGIN CERTIFICATE' not in public:
    raise SystemExit('Refusing invalid public CA export')
destination = Path('/ca-export/proxy-ca.pem')
destination.write_bytes(public)
destination.chmod(0o444)
PY
# Every HTTPS connection is intentionally opaque CONNECT in T02. Admission
# remains mandatory in CONNECT/server-connect hooks; no content is logged.
exec mitmdump --quiet --mode regular --listen-host 0.0.0.0 --listen-port 8080 \
    --set confdir=/home/mitmproxy/.mitmproxy --set connection_strategy=lazy \
    --set http2=false --set flow_detail=0 --set termlog_verbosity=error \
    --ignore-hosts '.*' -s /opt/aictrl/enforcer.py
