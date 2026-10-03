# Adapted from mattolson/agent-sandbox images/base/Dockerfile.
# MIT, Copyright (c) 2026 Matt Olson; see ../LICENSE.agent-sandbox.
ARG PYTHON_IMAGE=python:3.12.15-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3
FROM ${PYTHON_IMAGE}

# Dated, signed package repositories make apt dependencies reproducible.
ARG APT_SNAPSHOT=20261002T000000Z
RUN rm -f /etc/apt/sources.list.d/debian.sources && \
    printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/%s/ bookworm main\ndeb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/%s/ bookworm-security main\n' \
      "$APT_SNAPSHOT" "$APT_SNAPSHOT" > /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates curl git iptables iproute2 jq libstdc++6 openssl ripgrep util-linux zstd && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 501 dev && \
    useradd --create-home --uid 501 --gid 501 --shell /bin/bash dev && \
    mkdir -p /workspace /home/dev/.claude /etc/aictrl && \
    chown -R dev:dev /workspace /home/dev/.claude && chmod 700 /home/dev/.claude

COPY init-firewall.sh install-proxy-ca.sh entrypoint.sh /usr/local/bin/
COPY LICENSE.agent-sandbox /usr/local/share/licenses/agent-sandbox/LICENSE
RUN chmod 755 /usr/local/bin/init-firewall.sh /usr/local/bin/install-proxy-ca.sh /usr/local/bin/entrypoint.sh

ENV LANG=C.UTF-8 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
WORKDIR /workspace
# Trusted bootstrap starts as root, then irrevocably drops IDs and capabilities.
# It rejects startup unless the supervisor supplies an explicit restricted mode.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["false"]
