# Adapted from agent-sandbox images/agents/claude/Dockerfile.
# MIT, Copyright (c) 2026 Matt Olson; see ../LICENSE.agent-sandbox.
ARG BASE_IMAGE=aictrl-base:py3.12.15-t02
FROM ${BASE_IMAGE}
USER dev
ARG CLAUDE_CODE_VERSION=2.1.285
ARG CLAUDE_INSTALLER_SHA256=3a68d3406cf674e17bed1733a4dcf37805e2e47d87417700007d7e1aa766a944
ARG CLAUDE_SHA256_AMD64=33dad1ec615a2e08cc78b494f05c110e49916de2c79d78ec8799ebf46b233d29
ARG CLAUDE_SHA256_ARM64=24fac77749bed3d91365d6b6915aa4b824e14318ecb6bc17adbc192f01c9173d
ARG TARGETARCH
SHELL ["/bin/bash", "-euo", "pipefail", "-c"]

# Keep upstream's official native installation mechanism. Pin its one mutable
# bootstrap version lookup to the target version, after verifying the script.
RUN curl -fsSL https://claude.ai/install.sh -o /tmp/claude-install.sh && \
    echo "$CLAUDE_INSTALLER_SHA256  /tmp/claude-install.sh" | sha256sum -c - && \
    python -c 'from pathlib import Path; p=Path("/tmp/claude-install.sh"); s=p.read_text(); old="version=$(download_file \"$DOWNLOAD_BASE_URL/latest\")"; assert s.count(old)==1; p.write_text(s.replace(old, "version=\"$TARGET\""))' && \
    bash /tmp/claude-install.sh "$CLAUDE_CODE_VERSION" && \
    case "$TARGETARCH" in \
      amd64) task_checksum="$CLAUDE_SHA256_AMD64" ;; \
      arm64) task_checksum="$CLAUDE_SHA256_ARM64" ;; \
      *) echo 'Unsupported architecture' >&2; exit 1 ;; \
    esac && \
    echo "$task_checksum  /home/dev/.local/bin/claude" | sha256sum -c - && \
    /home/dev/.local/bin/claude --version | grep -Fx "$CLAUDE_CODE_VERSION (Claude Code)" && \
    rm -f /tmp/claude-install.sh

ENV PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    CLAUDE_CONFIG_DIR=/home/dev/.claude \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    DISABLE_AUTOUPDATER=1 \
    DISABLE_UPDATES=1 \
    ENABLE_CLAUDEAI_MCP_SERVERS=false
USER root
# Trusted bootstrap must never search an agent-writable directory for helpers.
# Promote the officially installed binary to a root-owned executable location.
RUN install -D -m 0755 /home/dev/.local/bin/claude /usr/local/lib/aictrl/claude && \
    ln -s /usr/local/lib/aictrl/claude /usr/local/bin/claude && \
    rm -rf /home/dev/.local/bin/claude /home/dev/.local/share/claude
LABEL org.opencontainers.image.description="AI Control Layer Claude foundation" \
    org.opencontainers.image.source="https://github.com/mattolson/agent-sandbox" \
    org.opencontainers.image.revision="c5b65e7cbd8f5b3bbf4e3ea40900c0014eedfa04" \
    io.aictrl.claude-version="${CLAUDE_CODE_VERSION}"
