"""Official SDK v2 lifecycle/Streamable HTTP, behind AICTRL identity checks."""

from collections.abc import Callable

from mcp import types
from mcp.server.lowlevel import Server
from mcp.shared.exceptions import MCPError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from aictrl.contracts import DecisionAction
from aictrl.mcp.control import MCPBlocked, MCPControlService
from aictrl.reporting.sink import StoreFailure


def create_mcp_server(service: Callable[[], MCPControlService]) -> Server:
    async def list_tools(ctx, params):
        definitions = await service().list_tools()
        return types.ListToolsResult(tools=[types.Tool(name=d.name, description=d.description, input_schema=d.input_schema) for d in definitions])

    async def list_resources(ctx, params):
        definitions = await service().list_resources()
        return types.ListResourcesResult(resources=[types.Resource(uri=d.uri, name=d.name, mime_type='text/plain') for d in definitions])

    async def call_tool(ctx, params):
        try:
            value = await service().call_tool(params.name, dict(params.arguments or {}))
            return types.CallToolResult(content=[types.TextContent(type='text', text=value)])
        except MCPBlocked as error:
            return types.CallToolResult(is_error=True, content=[types.TextContent(type='text', text=str(error))])

    async def read_resource(ctx, params):
        value = await service().read_resource(str(params.uri))
        return types.ReadResourceResult(contents=[types.TextResourceContents(uri=params.uri, mime_type='text/plain', text=value)])

    server = Server('AICTRL protected demo', version='t06', on_list_tools=list_tools,
                    on_call_tool=call_tool, on_list_resources=list_resources, on_read_resource=read_resource)

    async def safe_errors(ctx, call_next):
        try:
            return await call_next(ctx)
        except MCPBlocked as error:
            raise MCPError(-32000, str(error)) from None
        except StoreFailure:
            raise MCPError(-32000, 'AICTRL MCP audit unavailable.') from None
        except Exception:
            raise MCPError(-32602, 'AICTRL MCP request invalid or unavailable.') from None
    server.middleware.append(safe_errors)
    return server


class MCPIdentityBoundary:
    def __init__(self, app, service: Callable[[], MCPControlService]) -> None:
        self.app, self.service = app, service

    async def __call__(self, scope, receive, send):
        request = Request(scope)
        service = self.service()
        if not service.session.accepts(request.headers.getlist('x-aictrl-session')):
            control = service.request('unsupported')
            status = 401
            try:
                await service.audit.record(control, DecisionAction.BLOCK, 'mcp.invalid_session')
            except StoreFailure:
                status = 503
            await JSONResponse({'error': 'AICTRL MCP identity unavailable.'}, status_code=status)(scope, receive, send)
            return
        await self.app()(scope, receive, send)


def http_app(server: Server):
    return server.streamable_http_app(stateless_http=True, json_response=True, max_request_body_size=1048576,
                                     transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                         allowed_hosts=['gateway', 'gateway:8000'], allowed_origins=[]))
