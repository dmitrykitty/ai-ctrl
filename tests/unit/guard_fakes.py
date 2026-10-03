"""Explicit offline semantic fixture; never a production fallback."""
from aictrl.guards.semantic import QUESTIONS, SemanticAssessment


class FakeSemanticProvider:
    def __init__(self, scores=None, error=None):
        self.scores = scores or dict.fromkeys(QUESTIONS, 0.01)
        self.error = error
        self.calls = []

    async def evaluate(self, segments):
        self.calls.append(segments)
        if self.error:
            raise self.error
        return SemanticAssessment(self.scores)
