"""Protocol headers without leaking control-plane identity upstream."""

HOP_BY_HOP = {b'connection', b'proxy-connection', b'keep-alive', b'te', b'trailer',
              b'transfer-encoding', b'upgrade', b'proxy-authenticate', b'proxy-authorization'}
REQUEST_HEADERS = {b'authorization', b'x-api-key', b'x-app', b'content-type', b'accept',
                   b'accept-encoding', b'user-agent', b'x-request-id'}


def strip_set(headers: list[tuple[bytes, bytes]]) -> set[bytes]:
    result = set(HOP_BY_HOP)
    for name, value in headers:
        if name.lower() == b'connection':
            result.update(part.strip().lower() for part in value.split(b','))
    return result


def request_headers(headers: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    blocked = strip_set(headers) | {b'host', b'content-length'}
    return [(name, value) for name, value in headers
            if name.lower() not in blocked
            and (name.lower() in REQUEST_HEADERS or name.lower().startswith((b'anthropic-', b'x-stainless-', b'x-claude-code-')))]


def response_headers(headers: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    blocked = strip_set(headers)
    return [(name, value) for name, value in headers
            if name.lower() not in blocked and not name.lower().startswith(b'x-aictrl-')]


def codex_request_headers(headers: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    blocked = strip_set(headers) | {b'host', b'content-length'}
    allowed = {b'authorization', b'content-type', b'accept', b'accept-encoding',
               b'user-agent', b'chatgpt-account-id', b'originator', b'session_id',
               b'x-request-id'}
    prefixes = (b'openai-', b'x-openai-', b'x-stainless-', b'x-codex-', b'x-oai-', b'x-client-')
    return [(name, value) for name, value in headers
            if name.lower() not in blocked and not name.lower().startswith(b'x-aictrl-')
            and (name.lower() in allowed or name.lower().startswith(prefixes))]
