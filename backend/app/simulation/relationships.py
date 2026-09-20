"""Relações do simulador, sem validade hidrogeológica demonstrada.

Coeficientes de memória são diários; níveis crescem para baixo da superfície.
"""
from dataclasses import dataclass

import numpy as np

RECHARGE_MEMORY = 0.955
RECHARGE_MIN = 0.03
RECHARGE_MAX = 1.20
STRESS_MEMORY = 0.986
DEFICIT_WEIGHT = 0.052
UTILIZATION_WEIGHT = 0.040


def recharge_step(previous, normalized_rain, efficiency):
    return np.clip(RECHARGE_MEMORY * previous + (1 - RECHARGE_MEMORY) *
                   normalized_rain * efficiency, RECHARGE_MIN, RECHARGE_MAX)


def stress_step(previous, deficit, excess_use, multiplier):
    return max(0.0, STRESS_MEMORY * previous + multiplier *
               (DEFICIT_WEIGHT * deficit + UTILIZATION_WEIGHT * excess_use))


# Centralized numerical assumptions for the demonstration (not calibration).


@dataclass(frozen=True)
class ModelParameters:
    year_days: float = 365.25
    rainfall_peak_day: int = 105
    rainfall_season_floor: float = 0.35
    rainfall_season_amplitude: float = 0.65
    temperature_phase_day: int = 260
    score_medium: float = 25
    score_high: float = 50
    score_critical: float = 75
    population_min: int = 25000
    population_max: int = 90000
    per_capita_min: float = 0.145
    per_capita_max: float = 0.205
    flow_min: float = 28.0
    flow_max: float = 82.0
    efficiency_min: float = 0.88
    efficiency_max: float = 0.98
    static_min: float = 10.0
    static_max: float = 31.0
    depth_extra_min: float = 42.0
    depth_extra_max: float = 105.0
    specific_drawdown_min: float = 0.045
    specific_drawdown_max: float = 0.125
    reference_recharge: float = 0.72
    wet_probability_base: float = 0.18
    wet_probability_season: float = 0.42
    rainfall_shape: float = 1.65
    rainfall_scale: float = 10.5
    rainfall_spatial_noise: float = 0.09
    recharge_rainfall_mm: float = 9.0
    normalized_rain_cap: float = 1.5
    demand_season_amplitude: float = 0.075
    weekend_demand: float = 0.975
    demand_noise: float = 0.025
    annual_population_growth: float = 1.008
    pressure_threshold: float = 0.62
    flow_floor: float = 0.72
    flow_stress_loss: float = 0.010
    failure_base: float = 0.0012
    failure_utilization_weight: float = 0.006
    failure_utilization_threshold: float = 0.75
    failure_stress_weight: float = 0.0018
    failure_probability_cap: float = 0.30
    failure_runtime_fraction_max: float = 0.32
    idle_hours_threshold: float = 0.25
    flow_noise: float = 0.012
    static_stress_weight: float = 1.75
    static_noise: float = 0.035
    bottom_clearance_m: float = 2.0
    drawdown_base: float = 0.55
    drawdown_utilization_weight: float = 0.45
    drawdown_memory: float = 0.97
    score_base: float = 7.0
    score_deficit_weight: float = 25.0
    score_utilization_weight: float = 25.0
    score_utilization_threshold: float = 0.45
    score_stress_weight: float = 8.5
    score_drawdown_weight: float = 4.0
    score_failure_penalty: float = 18.0


MODEL = ModelParameters()
