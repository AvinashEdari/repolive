from abc import ABC, abstractmethod

from app.schemas.analysis import DeterministicAnalysis, ExplanationResult


class ExplanationProvider(ABC):
    @abstractmethod
    async def explain(self, analysis: DeterministicAnalysis) -> ExplanationResult:
        """Explain structured findings without receiving repository contents or secrets."""


class DisabledExplanationProvider(ExplanationProvider):
    async def explain(self, analysis: DeterministicAnalysis) -> ExplanationResult:
        del analysis
        return ExplanationResult(
            enabled=False,
            provider="disabled",
            summary="Optional explanations are disabled; deterministic findings remain available.",
            label="deterministic fallback",
        )
