# Reuse the already qualified agent-sandbox-derived base. MIT attribution kept.
ARG BASE_IMAGE=aictrl-base:py3.12.15-t02@sha256:7b229dcd23ba00496574245973a8ef32a23aec99211b0db249d0e84bfacb1147
FROM ${BASE_IMAGE}
ARG CODEX_VERSION=0.159.3
ARG CODEX_SHA256=7d3889a49a53ecbd7ac10330f37cbf13b9eef8966d564f6660449b89278cc824
ARG BWRAP_SHA256=f7c730d20d7d13db8e4b858f9a5735614616ae5426edd2edacb3b8e58186cd93
SHELL ["/bin/bash", "-euo", "pipefail", "-c"]
RUN test "$(uname -m)" = x86_64 && \
    curl -fsSL --retry 2 "https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/codex-x86_64-unknown-linux-musl.zst" -o /tmp/codex.zst && \
    echo "$CODEX_SHA256  /tmp/codex.zst" | sha256sum -c - && \
    zstd -d /tmp/codex.zst -o /usr/local/bin/codex && chmod 755 /usr/local/bin/codex && \
    curl -fsSL --retry 2 "https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/bwrap-x86_64-unknown-linux-musl.zst" -o /tmp/bwrap.zst && \
    echo "$BWRAP_SHA256  /tmp/bwrap.zst" | sha256sum -c - && \
    zstd -d /tmp/bwrap.zst -o /usr/local/bin/bwrap && chmod 755 /usr/local/bin/bwrap && \
    codex --version | grep -Fx "codex-cli ${CODEX_VERSION}" && rm /tmp/*.zst && \
    mkdir -p /home/dev/.codex && chown dev:dev /home/dev/.codex && chmod 700 /home/dev/.codex
ARG CODE_MODE_SHA256=85fe4cc711712d3f5d3c37fad955c240acb9ce878c1c95d6f8b45028dcc36d7c
RUN curl -fsSL --retry 2 "https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/codex-code-mode-host-x86_64-unknown-linux-musl.zst" -o /tmp/code-mode-host.zst && \
    echo "$CODE_MODE_SHA256  /tmp/code-mode-host.zst" | sha256sum -c - && \
    zstd -d /tmp/code-mode-host.zst -o /usr/local/bin/codex-code-mode-host && \
    chmod 755 /usr/local/bin/codex-code-mode-host && rm /tmp/code-mode-host.zst
COPY base/entrypoint.sh base/prepare-codex-profile.py /usr/local/bin/
COPY codex/aictrl.config.toml /usr/local/share/aictrl/aictrl.config.toml
COPY codex/LICENSE.openai-codex /usr/local/share/licenses/openai-codex/LICENSE
COPY codex/COPYING.bubblewrap /usr/local/share/licenses/bubblewrap/COPYING
COPY codex/LICENSE.bubblewrap /usr/local/share/licenses/bubblewrap/LICENSE
ENV CODEX_HOME=/home/dev/.codex AICTRL_ADAPTER=codex
LABEL io.aictrl.codex-version="${CODEX_VERSION}" \
    org.opencontainers.image.source="https://github.com/openai/codex"
