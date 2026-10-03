"""Ordered deterministic privacy checks, then bounded external semantics."""

import asyncio
from dataclasses import replace
import math
from time import perf_counter_ns

from aictrl.contracts import DecisionAction, GuardResult, Severity
from aictrl.guards.models import GuardEvaluation, InspectionSegment, Replacement, aggregate
from aictrl.guards.pii import PiiGuard
from aictrl.guards.secrets import SecretGuard
from aictrl.guards.semantic import QUESTIONS, SemanticDecisionProvider
from aictrl.policy.models import GuardSettings


def result(guard: str, action: DecisionAction, reason: str, start: int,
           signatures: tuple[str, ...] = ()) -> GuardResult:
    return GuardResult(guard_id=guard, action=action, reason_code=reason, signature_ids=signatures,
                       severity=Severity.HIGH if action == DecisionAction.BLOCK else None,
                       latency_ms=(perf_counter_ns() - start) / 1_000_000)


class GuardEngine:
    def __init__(self, settings: GuardSettings, semantic: SemanticDecisionProvider | None = None) -> None:
        self.settings, self.semantic = settings, semantic
        self.secrets = SecretGuard()
        self.pii = PiiGuard(settings.pii.entities)

    async def inspect_input(self, segments: tuple[InspectionSegment, ...]) -> GuardEvaluation:
        return await self._inspect(segments, output=False, semantic=True)

    async def inspect_output(self, segments: tuple[InspectionSegment, ...], *, semantic: bool = False) -> GuardEvaluation:
        return await self._inspect(segments, output=True, semantic=semantic)

    async def _inspect(self, segments: tuple[InspectionSegment, ...], *, output: bool, semantic: bool) -> GuardEvaluation:
        results: list[GuardResult] = []
        start = perf_counter_ns()
        signatures = tuple(dict.fromkeys(signature for text in (
            *(segment.text for segment in segments), ''.join(segment.text for segment in segments))
            for signature in self.secrets.scan(text))) if self.settings.secrets.enabled else ()
        results.append(result('guard.secret', DecisionAction.BLOCK if signatures else DecisionAction.ALLOW,
                              'guard.secret.detected' if signatures else 'guard.secret.safe', start, signatures))
        if signatures:
            return GuardEvaluation(DecisionAction.BLOCK, tuple(results))
        start = perf_counter_ns()
        replacements: list[Replacement] = []
        semantic_segments: list[InspectionSegment] = []
        entities: set[str] = set()
        immutable_pii = False
        for segment in segments:
            findings = self.pii.scan(segment.text) if self.settings.pii.enabled else ()
            entities.update(f.entity for f in findings)
            redacted = self.pii.redact(segment.text, findings)
            if findings:
                immutable_pii |= not segment.mutable
                replacements.append(Replacement(segment.json_path, redacted))
            if segment.untrusted_external:
                semantic_segments.append(replace(segment, text=redacted))
        pii_action = DecisionAction.BLOCK if entities and (output or immutable_pii) else DecisionAction.REDACT if entities else DecisionAction.ALLOW
        results.append(result('guard.pii', pii_action,
                              ('guard.pii.output_blocked' if output else 'guard.pii.input_immutable') if pii_action == DecisionAction.BLOCK else 'guard.pii.redacted' if entities else 'guard.pii.safe', start,
                              tuple('pii.' + entity.lower() for entity in sorted(entities))))
        if pii_action == DecisionAction.BLOCK:
            return GuardEvaluation(DecisionAction.BLOCK, tuple(results))
        if semantic and self.settings.semantic.enabled and semantic_segments:
            start = perf_counter_ns()
            if len(semantic_segments) > 256 or sum(len(segment.text) for segment in semantic_segments) > self.settings.semantic.max_chars:
                results.append(result('guard.semantic', DecisionAction.BLOCK, 'guard.semantic.input_too_large', start))
            else:
                try:
                    if self.semantic is None:
                        raise ValueError('Missing semantic provider')
                    async with asyncio.timeout(self.settings.semantic.timeout_ms / 1000):
                        assessment = await self.semantic.evaluate(tuple(semantic_segments))
                    scores = assessment.probabilities
                    if set(scores) != set(QUESTIONS) or any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1 for v in scores.values()):
                        raise ValueError('Invalid semantic assessment')
                    for name in QUESTIONS:
                        blocked = scores[name] >= getattr(self.settings.semantic.thresholds, name)
                        results.append(result('guard.semantic', DecisionAction.BLOCK if blocked else DecisionAction.ALLOW,
                                              'guard.semantic.' + name if blocked else 'guard.semantic.safe', start))
                except Exception:
                    results.append(result('guard.semantic', DecisionAction.BLOCK, 'guard.semantic.unavailable', start))
        action = aggregate([r.action for r in results])
        return GuardEvaluation(action, tuple(results), tuple(replacements) if action == DecisionAction.REDACT else ())
