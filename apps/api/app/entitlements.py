from dataclasses import dataclass
from typing import Literal

PlanCode = Literal["free", "pro"]


@dataclass(frozen=True)
class Entitlements:
    plan: PlanCode
    monthly_analyses: int
    history_days: int
    advanced_comparisons: bool
    deeper_compatibility: bool
    private_repositories: bool
    api_requests: int
    team_members: int


PLANS: dict[PlanCode, Entitlements] = {
    "free": Entitlements("free", 50, 90, False, False, False, 100, 1),
    "pro": Entitlements("pro", 1000, 365, True, True, True, 10_000, 10),
}


def entitlements_for(plan: str | None) -> Entitlements:
    return PLANS["pro"] if plan == "pro" else PLANS["free"]
