from dataclasses import dataclass

VERSION = "multicriteria-v1.0.0"
MIN_COVERAGE = 0.8
CLASSIFICATION_LIMITS = ((80, "CRITICAL"), (60, "HIGH"), (40, "ATTENTION"), (0, "NORMAL"))


@dataclass(frozen=True)
class Criterion:
    section: str
    key: str
    low: float
    high: float
    direction: int = 1


# Demonstration anchors, not calibrated hydrogeological thresholds.
GROUPS = {
    "groundwater": ("Estresse subterrâneo", .30, (
        Criterion("groundwater", "static_level_trend_30d", 0, .10),
        Criterion("groundwater", "drawdown_trend_30d", 0, .10),
        Criterion("operations", "flow_trend_30d", 0, .10, -1),
    )),
    "rainfall": ("Déficit de precipitação", .20, (
        Criterion("rainfall", "recent_rainfall_deficit_30d", 0, 1),
    )),
    "demand": ("Pressão de demanda", .20, (
        Criterion("operations", "demand_pressure_30d", 0, .50),
    )),
    "pumping": ("Pressão de bombeamento", .20, (
        Criterion("operations", "pumping_hours_avg_30d", 8, 24),
        Criterion("operations", "utilization_avg_30d", .50, 1),
    )),
    "operations": ("Estresse operacional", .10, (
        Criterion("operations", "failures_30d", 0, 10),
    )),
}
