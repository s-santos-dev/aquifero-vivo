"""Parâmetros demonstrativos; não calibrados cientificamente."""
from dataclasses import dataclass
from enum import StrEnum

class Scenario(StrEnum):
    NORMAL = "NORMAL"
    DROUGHT = "DROUGHT"
    SEVERE_STRESS = "SEVERE_STRESS"


@dataclass(frozen=True)
class ScenarioParameters:
    rainfall_multiplier: float
    demand_multiplier: float
    recharge_efficiency: float
    stress_multiplier: float
    failure_multiplier: float


SCENARIO_PARAMETERS = {
    Scenario.NORMAL: ScenarioParameters(1.00, 1.00, 1.00, 1.00, 1.00),
    Scenario.DROUGHT: ScenarioParameters(0.52, 1.12, 0.82, 1.28, 1.55),
    Scenario.SEVERE_STRESS: ScenarioParameters(0.24, 1.28, 0.62, 1.72, 2.30),
}


