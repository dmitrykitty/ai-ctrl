"""Trusted sessions without a native inference transport deny every LLM route."""

from aictrl.contracts import Channel, Direction, InspectionLevel


class MCPOnlyHandler:
    protocol = None
    channel = Channel.LLM
    direction = Direction.OUTBOUND
    inspection_level = InspectionLevel.STRUCTURED
    target = 'unsupported'

    def resolve_operation(self, method: str, path: str) -> None:
        return None
