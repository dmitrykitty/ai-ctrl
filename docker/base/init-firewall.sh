#!/usr/bin/env bash
# Adapted from agent-sandbox images/base/init-firewall.sh (MIT, Matt Olson 2026).
# See LICENSE.agent-sandbox. Only explicit proxy/gateway TCP sockets are allowed.
set -euo pipefail

[[ "$(id -u)" == 0 ]] || { echo 'Firewall setup requires trusted root bootstrap' >&2; exit 1; }
python - <<'PY'
import ipaddress
import os
mode = os.environ.get('AICTRL_BOOTSTRAP_MODE')
if mode not in ('auth', 'runtime'):
    raise SystemExit('An explicit auth or runtime bootstrap mode is required')
names = ['AICTRL_PROXY_IP']
if mode == 'runtime' and os.environ.get('AICTRL_GATEWAY_IP'):
    names.append('AICTRL_GATEWAY_IP')
for name in names:
    address = ipaddress.IPv4Address(os.environ[name])
    if not address.is_private or address.is_loopback or address.is_unspecified:
        raise SystemExit('Proxy/gateway must have a designated private IPv4 address')
PY

# Set default deny BEFORE flushing; no temporary permissive interval.
for table in iptables ip6tables; do
    "$table" -P INPUT DROP
    "$table" -P FORWARD DROP
    "$table" -P OUTPUT DROP
    "$table" -F
    "$table" -X
done

# Keep Docker NAT rules, but never permit traffic to its embedded DNS listener.
# Host entries supply gateway/proxy names. External DNS resolution is proxy-only.
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -i lo -s 127.0.0.1/32 -p tcp -j ACCEPT
iptables -A OUTPUT -o lo -d 127.0.0.1/32 -p tcp -j ACCEPT
iptables -A OUTPUT -d "$AICTRL_PROXY_IP/32" -p tcp --dport 8080 -j ACCEPT
if [[ "$AICTRL_BOOTSTRAP_MODE" == runtime && -n "${AICTRL_GATEWAY_IP:-}" ]]; then
    iptables -A OUTPUT -d "$AICTRL_GATEWAY_IP/32" -p tcp --dport 8000 -j ACCEPT
fi
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited
ip6tables -A OUTPUT -j REJECT --reject-with icmp6-adm-prohibited

# A live proxy socket is a prerequisite; do not launch if enforcement is absent.
for attempt in {1..30}; do
    if timeout 1 bash -c 'exec 3<>/dev/tcp/"$AICTRL_PROXY_IP"/8080' 2>/dev/null; then
        echo 'Restricted firewall initialized'
        exit 0
    fi
    sleep 1
done
echo 'Required proxy is unreachable; refusing agent startup' >&2
exit 1
