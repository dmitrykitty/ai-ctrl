#!/usr/bin/env bash
# Adapted from agent-sandbox images/base/install-proxy-ca.sh (MIT, Matt Olson 2026).
set -euo pipefail
task_ca=/etc/aictrl/proxy-ca.pem
task_destination=/usr/local/share/ca-certificates/aictrl-proxy.crt
[[ -f "$task_ca" ]] || { echo 'Required public proxy CA is absent' >&2; exit 1; }
if grep -q 'PRIVATE KEY' "$task_ca"; then
    echo 'Refusing private key material in public CA mount' >&2
    exit 1
fi
openssl x509 -in "$task_ca" -noout >/dev/null
cp "$task_ca" "$task_destination"
update-ca-certificates --fresh >/dev/null
