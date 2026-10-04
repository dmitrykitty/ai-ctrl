"""Small native transport contract; no admission/policy/persistence behavior."""

from typing import Protocol

import httpx

from aictrl.contracts import AgentProtocol, Channel, Direction, InspectionLevel
from aictrl.guards.models import InspectionSegment


class StreamObserver(Protocol):
    completed: bool
    failed: bool

    def observe(self, chunk: bytes) -> None: ...


class NativeProtocolHandler(Protocol):
    protocol: AgentProtocol
    channel: Channel
    direction: Direction
    inspection_level: InspectionLevel
    target: str

    def resolve_operation(self, method: str, path: str) -> str | None: ...

    def validate_payload(self, payload: object, operation: str) -> bool: ...

    def extract_inspection(self, payload: dict) -> tuple[InspectionSegment, ...]: ...

    def new_output_buffer(self, max_bytes: int): ...

    def build_upstream_url(self, operation: str, raw_query: bytes) -> httpx.URL: ...

    def filter_request_headers(self, headers: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]: ...

    def new_stream_observer(self) -> StreamObserver | None: ...

    def new_usage_collector(self, operation: str): ...

    def token_reservation(self, payload: dict, settings) -> int: ...
