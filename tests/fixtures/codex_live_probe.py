"""One bounded native Codex experiment; emit only whitelisted safe evidence."""
import json
import os
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from uuid import UUID

PREFIX = 'AICTRL_CODEX_LIVE '
EXPECTED = 'AICTRL_CODEX_OK'


def native_evidence(code: int, stdout: str, stderr: str) -> dict:
    # Native errors may contain a body/token or the complete prompt. Never emit
    # lines or fragments: only fixed classifications and numeric HTTP statuses.
    statuses = sorted({int(value) for value in re.findall(r'(?:status(?: code)?[ :]*(?:HTTP[^ ]* )?|HTTP/\S+\s+)([45][0-9]{2})',stderr,re.I)})
    lower = stderr.lower()
    return {'native_exit':code,'exact_response':stdout.strip() == EXPECTED,
            'http_statuses':statuses,
            'invalid_api_key':'invalid_api_key' in lower,
            'missing_model_request_scope':'model.request' in lower and ('missing' in lower or 'scope' in lower),
            'unsupported_authentication':'unsupported authentication' in lower,
            'configuration_error':'error loading config' in lower or 'unknown configuration' in lower}


def main() -> None:
    try:
        native = subprocess.run(['codex','--no-daemon','--profile','aictrl','exec','--skip-git-repo-check',
                                 '--ephemeral','--color','never'],input=sys.stdin.read(),capture_output=True,text=True,timeout=60)
        result = native_evidence(native.returncode,native.stdout,native.stderr)
    except (OSError,subprocess.SubprocessError):
        result = native_evidence(124,'','')
    result.update(forbidden_status=-1,forbidden_request_id=None,direct_blocked=False,proxy_denied=False)
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request('http://gateway:8000/codex/responses',method='GET',
                                         headers={'X-AICtrl-Session':os.environ['AICTRL_SESSION_TOKEN']})
        try:
            with opener.open(request,timeout=5) as response: result['forbidden_status']=response.status
        except urllib.error.HTTPError as error:
            result['forbidden_status']=error.code
            result['forbidden_request_id']=str(UUID(json.load(error)['request_id']))
    except (OSError,ValueError,KeyError,TypeError): pass
    try:
        with socket.create_connection(('1.1.1.1',443),timeout=2): pass
    except OSError: result['direct_blocked']=True
    try:
        with socket.create_connection((os.environ['AICTRL_PROXY_IP'],8080),timeout=3) as connection:
            connection.sendall(b'CONNECT api.openai.com:443 HTTP/1.1\r\nHost: api.openai.com:443\r\n\r\n')
            result['proxy_denied']=b' 403 ' in connection.recv(4096).split(b'\r\n',1)[0]
    except OSError: pass
    print(PREFIX+json.dumps(result),flush=True)


if __name__ == '__main__': main()
