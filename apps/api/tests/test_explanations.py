import pytest

from app.explanations.base import DisabledExplanationProvider
from app.schemas.analysis import DeterministicAnalysis, QualitySignals


@pytest.mark.asyncio
async def test_disabled_explanation_provider_keeps_product_functional() -> None:
    analysis = DeterministicAnalysis(
        languages=[],
        technologies=[],
        important_files=[],
        project_types=["General software repository"],
        dependencies=[],
        runtimes=[],
        quality=QualitySignals(
            has_readme=False,
            has_license=False,
            has_tests=False,
            has_ci=False,
            has_container_config=False,
            has_environment_example=False,
        ),
        scores=[],
    )
    result = await DisabledExplanationProvider().explain(analysis)
    assert result.enabled is False
    assert result.label == "deterministic fallback"
