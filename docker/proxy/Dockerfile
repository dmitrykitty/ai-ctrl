# Adapted from agent-sandbox images/proxy/Dockerfile (MIT, Matt Olson 2026).
ARG MITMPROXY_IMAGE=mitmproxy/mitmproxy@sha256:00b77b5d8804c8ad18cb6caefbf9d5849e895e8986c5ce011f4ae30f4385962f
FROM ${MITMPROXY_IMAGE}
USER root
RUN mkdir -p /home/mitmproxy/.mitmproxy /ca-export /opt/aictrl && \
    chown -R 1000:1000 /home/mitmproxy /ca-export && \
    chmod 700 /home/mitmproxy/.mitmproxy
COPY destinations.py enforcer.py entrypoint.sh /opt/aictrl/
COPY LICENSE.agent-sandbox /usr/local/share/licenses/agent-sandbox/LICENSE
USER 1000:1000
ENV HOME=/home/mitmproxy
ENTRYPOINT ["/bin/bash", "/opt/aictrl/entrypoint.sh"]
