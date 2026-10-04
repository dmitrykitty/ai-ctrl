# Qualified immutable base; no provider binary or credential volume.
FROM aictrl-base:py3.12.15-t02@sha256:7b229dcd23ba00496574245973a8ef32a23aec99211b0db249d0e84bfacb1147
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --chmod=755 init-firewall.sh /usr/local/bin/init-firewall.sh
COPY main.py governance.py /opt/aictrl/demo/agent/
ENV AICTRL_ADAPTER=demo-agent PYTHONDONTWRITEBYTECODE=1
CMD ["python", "/opt/aictrl/demo/agent/main.py"]
