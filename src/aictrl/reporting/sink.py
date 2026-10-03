"""Durable write boundary, independent of the reporting query backend."""

from typing import Protocol, runtime_checkable

from aictrl.contracts import SecurityEvent


class StoreFailure(RuntimeError):
    """The requested event could not be durably committed."""


@runtime_checkable
class EventSink(Protocol):
    def append(self, event: SecurityEvent) -> None:
        """Commit durably before returning; raise StoreFailure on failure.

        Security-critical admission uses this synchronous guarantee. Queuing
        an event for later writing does not satisfy this contract.
        """
        ...
