"""Selected Presidio recognizers called directly: no NLP engine or downloads."""

from dataclasses import dataclass

from presidio_analyzer import PatternRecognizer
from presidio_analyzer.predefined_recognizers import CreditCardRecognizer, EmailRecognizer, PhoneRecognizer


@dataclass(frozen=True)
class PiiFinding:
    start: int
    end: int
    entity: str


class PiiGuard:
    def __init__(self, entities: tuple[str, ...]) -> None:
        # EmailRecognizer's validation consults tldextract's remote PSL. Reuse
        # its selected regex through PatternRecognizer instead, entirely local.
        available = {
            'EMAIL_ADDRESS': PatternRecognizer(supported_entity='EMAIL_ADDRESS', patterns=EmailRecognizer.PATTERNS),
            'CREDIT_CARD': CreditCardRecognizer(),
            'PHONE_NUMBER': PhoneRecognizer(supported_regions=('US', 'GB', 'DE', 'FR'), leniency=1),
        }
        self.recognizers = tuple(available[entity] for entity in entities)
        self.entities = list(entities)

    def scan(self, text: str) -> tuple[PiiFinding, ...]:
        findings = {PiiFinding(r.start, r.end, r.entity_type) for recognizer in self.recognizers
                    for r in recognizer.analyze(text, self.entities, nlp_artifacts=None) if r.score > 0}
        # Prefer the earliest, longest match; card wins a same-span phone tie.
        ordered = sorted(findings, key=lambda f: (f.start, -f.end, f.entity))
        selected: list[PiiFinding] = []
        for finding in ordered:
            if not selected or finding.start >= selected[-1].end:
                selected.append(finding)
        return tuple(selected)

    @staticmethod
    def redact(text: str, findings: tuple[PiiFinding, ...]) -> str:
        for finding in reversed(findings):
            text = text[:finding.start] + '[REDACTED_' + finding.entity + ']' + text[finding.end:]
        return text
