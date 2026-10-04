"""Bounded per-operation timings; original streams remain unmodified."""

from contextlib import contextmanager
import logging
from time import perf_counter_ns

from aictrl.contracts import ControlRequest
from aictrl.guards.models import GuardEvaluation
from aictrl.reporting.service import ReportingStore
from aictrl.reporting.sink import StoreFailure

logger = logging.getLogger('aictrl.reporting')


class Timings:
    def __init__(self, reporting: ReportingStore | None) -> None:
        self.reporting = reporting
        self.started = perf_counter_ns()
        self.request: ControlRequest | None = None
        self.samples: dict[str, float] = {}
        self.finished = False

    def add(self, stage: str, milliseconds: float) -> None:
        self.samples[stage] = self.samples.get(stage, 0) + max(0, milliseconds)

    @contextmanager
    def span(self, stage: str):
        start = perf_counter_ns()
        try:
            yield
        finally:
            self.add(stage, (perf_counter_ns()-start)/1000000)

    def guards(self, evaluation: GuardEvaluation, started: int) -> None:
        elapsed = (perf_counter_ns()-started)/1000000
        semantic = max((result.latency_ms for result in evaluation.results if result.guard_id == 'guard.semantic'), default=0)
        self.add('deterministic_guards', elapsed-semantic)
        if any(result.guard_id == 'guard.semantic' for result in evaluation.results):
            self.add('semantic_jev', semantic)

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        self.add('total', (perf_counter_ns()-self.started)/1000000)
        if self.reporting is not None and self.request is not None:
            try:
                self.reporting.latency(self.request.session_id, self.request.request_id, self.samples)
            except StoreFailure:
                # Timing is observational; never change an admission decision
                # or fabricate a sample after a telemetry write failure.
                logger.warning('Reporting timing unavailable for session %s request %s', self.request.session_id, self.request.request_id)
