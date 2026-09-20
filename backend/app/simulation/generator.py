"""Gerador causal e reproduzível de séries operacionais sintéticas.

Os níveis são profundidades abaixo da superfície: valores maiores representam
níveis d'água mais baixos. Nenhum registro produzido aqui é uma observação real.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from app.data_provenance import SIMULATION_SOURCE


from app.simulation.config import SimulationConfig
from app.simulation.scenarios import Scenario, SCENARIO_PARAMETERS
from app.simulation.relationships import MODEL, recharge_step, stress_step

GENERATOR_VERSION = "2.0.0"
DATA_CLASSIFICATION = "SIMULATED"


@dataclass
class SyntheticDataset:
    config: SimulationConfig
    sectors: list[dict[str, Any]]
    wells: list[dict[str, Any]]
    sector_daily: list[dict[str, Any]]
    well_daily: list[dict[str, Any]]

    @property
    def counts(self) -> dict[str, int]:
        return {
            "sectors": len(self.sectors),
            "wells": len(self.wells),
            "sector_daily": len(self.sector_daily),
            "well_daily": len(self.well_daily),
        }


def _rounded(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def _risk_level(score: float) -> str:
    if score >= MODEL.score_critical:
        return "CRITICAL"
    if score >= MODEL.score_high:
        return "HIGH"
    if score >= MODEL.score_medium:
        return "MEDIUM"
    return "LOW"


def _rainfall_seasonality(day: date) -> float:
    # Pico aproximadamente em abril; mantém chuva residual no segundo semestre.
    angle = 2 * math.pi * (day.timetuple().tm_yday - MODEL.rainfall_peak_day) / MODEL.year_days
    return MODEL.rainfall_season_floor + MODEL.rainfall_season_amplitude * ((math.cos(angle) + 1) / 2)


def _base_record(config: SimulationConfig) -> dict[str, Any]:
    return {
        "source": SIMULATION_SOURCE,
        "data_classification": DATA_CLASSIFICATION,
        "is_synthetic": True,
        "scenario": config.scenario.value,
        "simulation_seed": config.seed,
        "generator_version": GENERATOR_VERSION,
    }


def generate_dataset(config: SimulationConfig = SimulationConfig()) -> SyntheticDataset:
    """Gera um dataset em memória usando apenas o gerador pseudoaleatório local."""

    rng = np.random.default_rng(config.seed)
    params = SCENARIO_PARAMETERS[config.scenario]
    common = _base_record(config)

    sector_populations = rng.integers(MODEL.population_min, MODEL.population_max + 1, config.sector_count)
    per_capita = rng.uniform(MODEL.per_capita_min, MODEL.per_capita_max, config.sector_count)
    sector_lat = rng.uniform(config.min_latitude, config.max_latitude, config.sector_count)
    sector_lon = rng.uniform(config.min_longitude, config.max_longitude, config.sector_count)

    strip_width = (config.max_longitude - config.min_longitude) / config.sector_count
    sector_lon = np.array([config.min_longitude + (i + 0.5) * strip_width for i in range(config.sector_count)])
    sector_lat[:] = (config.min_latitude + config.max_latitude) / 2
    sectors: list[dict[str, Any]] = []
    for index in range(config.sector_count):
        sectors.append(
            {
                **common,
                "sector_id": f"SIM-SEC-{index + 1:03d}",
                "name": f"Setor Sintético {index + 1:03d}",
                "population_base": int(sector_populations[index]),
                "west": config.min_longitude + index * strip_width,
                "east": config.min_longitude + (index + 1) * strip_width,
                "south": config.min_latitude,
                "north": config.max_latitude,
                "latitude": float(sector_lat[index]),
                "longitude": float(sector_lon[index]),
            }
        )

    # A atribuição modular garante pelo menos um poço por setor.
    sector_indexes = np.arange(config.well_count) % config.sector_count
    rng.shuffle(sector_indexes)
    well_capacity = rng.uniform(MODEL.flow_min, MODEL.flow_max, config.well_count)
    well_efficiency = rng.uniform(MODEL.efficiency_min, MODEL.efficiency_max, config.well_count)
    well_static_base = rng.uniform(MODEL.static_min, MODEL.static_max, config.well_count)
    well_depth = well_static_base + rng.uniform(MODEL.depth_extra_min, MODEL.depth_extra_max, config.well_count)
    well_specific_drawdown = rng.uniform(MODEL.specific_drawdown_min, MODEL.specific_drawdown_max, config.well_count)

    wells: list[dict[str, Any]] = []
    for index in range(config.well_count):
        sector_index = int(sector_indexes[index])
        wells.append(
            {
                **common,
                "well_id": f"SIM-PI-{index + 1:03d}",
                "sector_id": f"SIM-SEC-{sector_index + 1:03d}",
                "name": f"Poço Sintético {index + 1:04d}",
                "latitude": float(rng.uniform(config.min_latitude, config.max_latitude)),
                "longitude": float(rng.uniform(config.min_longitude + sector_index * strip_width, config.min_longitude + (sector_index + 1) * strip_width)),
                "depth_m": _rounded(well_depth[index], 2),
                "nominal_flow_m3_h": _rounded(well_capacity[index], 3),
            }
        )

    sector_wells = [np.flatnonzero(sector_indexes == i) for i in range(config.sector_count)]
    dates = [config.start_date + timedelta(days=offset) for offset in range(config.days)]
    sector_daily: list[dict[str, Any]] = []
    sector_state: dict[tuple[int, int], tuple[float, float, float]] = {}
    recharge = np.full(config.sector_count, MODEL.reference_recharge)

    for day_index, current_date in enumerate(dates):
        seasonal_rain = _rainfall_seasonality(current_date)
        # As mesmas realizações base são escaladas pelos cenários.
        wet_event = rng.random(config.sector_count) < (MODEL.wet_probability_base + MODEL.wet_probability_season * seasonal_rain)
        base_rain = wet_event * rng.gamma(MODEL.rainfall_shape, MODEL.rainfall_scale * seasonal_rain, config.sector_count)
        spatial_factor = rng.normal(1.0, MODEL.rainfall_spatial_noise, config.sector_count)
        precipitation = np.maximum(0.0, base_rain * spatial_factor * params.rainfall_multiplier)

        normalized_rain = np.clip(precipitation / MODEL.recharge_rainfall_mm, 0.0, MODEL.normalized_rain_cap)
        recharge = recharge_step(recharge, normalized_rain, params.recharge_efficiency)
        temperature_cycle = math.sin(2 * math.pi * (current_date.timetuple().tm_yday - MODEL.temperature_phase_day) / MODEL.year_days)
        demand_weather = 1.0 + MODEL.demand_season_amplitude * temperature_cycle
        weekend_factor = MODEL.weekend_demand if current_date.weekday() >= 5 else 1.0
        demand_noise = rng.normal(1.0, MODEL.demand_noise, config.sector_count)
        population_growth = MODEL.annual_population_growth ** (day_index / MODEL.year_days)
        population = np.rint(sector_populations * population_growth).astype(int)
        demand = (
            population
            * per_capita
            * demand_weather
            * weekend_factor
            * demand_noise
            * params.demand_multiplier
        )

        for sector_index in range(config.sector_count):
            total_daily_capacity = float(
                np.sum(well_capacity[sector_wells[sector_index]] * 24 * well_efficiency[sector_wells[sector_index]])
            )
            utilization = float(demand[sector_index] / total_daily_capacity)
            sector_state[(day_index, sector_index)] = (
                float(demand[sector_index]),
                utilization,
                float(recharge[sector_index]),
            )
            sector_daily.append(
                {
                    **common,
                    "date": current_date.isoformat(),
                    "sector_id": f"SIM-SEC-{sector_index + 1:03d}",
                    "population_served": int(population[sector_index]),
                    "daily_demand_m3": _rounded(demand[sector_index]),
                    "precipitation_mm": _rounded(precipitation[sector_index]),
                    "recharge_index": _rounded(recharge[sector_index], 5),
                    "system_utilization": _rounded(utilization, 5),
                }
            )

    well_daily: list[dict[str, Any]] = []
    stress_stock = np.zeros(config.well_count)
    persistent_drawdown = np.zeros(config.well_count)

    for day_index, current_date in enumerate(dates):
        for sector_index, member_indexes in enumerate(sector_wells):
            demand, sector_utilization, recharge_index = sector_state[(day_index, sector_index)]
            capacities = well_capacity[member_indexes] * well_efficiency[member_indexes]
            allocation = capacities / capacities.sum()
            requested_volume = demand * allocation

            for local_index, well_index_value in enumerate(member_indexes):
                well_index = int(well_index_value)
                requested_runtime = requested_volume[local_index] / max(capacities[local_index], 0.1)
                utilization = float(requested_runtime / 24.0)
                deficit = max(0.0, MODEL.reference_recharge - recharge_index)
                excess_use = max(0.0, utilization - MODEL.pressure_threshold)
                stress_stock[well_index] = stress_step(
                    stress_stock[well_index], deficit, excess_use, params.stress_multiplier
                )

                available_flow = well_capacity[well_index] * max(
                    MODEL.flow_floor, 1.0 - MODEL.flow_stress_loss * stress_stock[well_index]
                )
                base_failure_probability = (
                    MODEL.failure_base
                    + MODEL.failure_utilization_weight * max(0.0, utilization - MODEL.failure_utilization_threshold)
                    + MODEL.failure_stress_weight * stress_stock[well_index]
                ) * params.failure_multiplier
                failed = bool(rng.random() < min(base_failure_probability, MODEL.failure_probability_cap))
                failure_fraction = float(rng.uniform(0.0, MODEL.failure_runtime_fraction_max))
                failure_kind = rng.choice(["PUMP_FAILURE", "POWER_OUTAGE", "MAINTENANCE"])
                if failed:
                    runtime = min(24.0, requested_runtime) * failure_fraction
                    failure_type = failure_kind
                    status = "FAILED"
                else:
                    runtime = min(24.0, requested_runtime)
                    failure_type = "NONE"
                    status = "OPERATING" if runtime > MODEL.idle_hours_threshold else "IDLE"

                flow_noise = float(rng.normal(1.0, MODEL.flow_noise))
                flow_rate = max(0.0, available_flow * flow_noise)
                pumped_volume = flow_rate * runtime
                static_level = (
                    well_static_base[well_index]
                    + MODEL.static_stress_weight * stress_stock[well_index]
                    + rng.normal(0.0, MODEL.static_noise)
                )
                pumping_drawdown = well_specific_drawdown[well_index] * flow_rate * (MODEL.drawdown_base + MODEL.drawdown_utilization_weight * utilization)
                static_level = min(well_depth[well_index] - MODEL.bottom_clearance_m, max(0.0, static_level))
                dynamic_level = min(well_depth[well_index] - MODEL.bottom_clearance_m, static_level + pumping_drawdown)
                actual_drawdown = max(0.0, dynamic_level - static_level)
                persistent_drawdown[well_index] = (
                    MODEL.drawdown_memory * persistent_drawdown[well_index] + (1 - MODEL.drawdown_memory) * actual_drawdown
                )

                risk_score = float(
                    np.clip(
                        MODEL.score_base
                        + MODEL.score_deficit_weight * deficit
                        + MODEL.score_utilization_weight * max(0.0, utilization - MODEL.score_utilization_threshold)
                        + MODEL.score_stress_weight * stress_stock[well_index]
                        + MODEL.score_drawdown_weight * persistent_drawdown[well_index]
                        + (MODEL.score_failure_penalty if failed else 0.0),
                        0.0,
                        100.0,
                    )
                )
                well_daily.append(
                    {
                        **common,
                        "date": current_date.isoformat(),
                        "well_id": f"SIM-PI-{well_index + 1:03d}",
                        "sector_id": f"SIM-SEC-{sector_index + 1:03d}",
                        "daily_demand_m3": _rounded(requested_volume[local_index]),
                        "flow_rate_m3_h": _rounded(flow_rate),
                        "static_level_m": _rounded(static_level),
                        "dynamic_level_m": _rounded(dynamic_level),
                        "drawdown_m": _rounded(actual_drawdown),
                        "pumped_volume_m3": _rounded(pumped_volume),
                        "runtime_hours": _rounded(runtime),
                        "utilization": _rounded(utilization, 5),
                        "recharge_index": _rounded(recharge_index, 5),
                        "operating_status": status,
                        "operational_failure": failed,
                        "failure_type": str(failure_type),
                        "risk_score": _rounded(risk_score, 2),
                        "risk_level": _risk_level(risk_score),
                    }
                )

    return SyntheticDataset(config, sectors, wells, sector_daily, well_daily)


def _write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def write_dataset(dataset: SyntheticDataset, output_dir: str | Path) -> Path:
    """Grava quatro CSVs e um manifesto inequívoco de proveniência."""

    target = Path(output_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    files = {
        "sectors.csv": dataset.sectors,
        "wells.csv": dataset.wells,
        "sector_daily.csv": dataset.sector_daily,
        "well_daily.csv": dataset.well_daily,
    }
    checksums: dict[str, str] = {}
    for filename, records in files.items():
        path = target / filename
        _write_csv(path, records)
        checksums[filename] = hashlib.sha256(path.read_bytes()).hexdigest()

    config_payload = asdict(dataset.config)
    config_payload["scenario"] = dataset.config.scenario.value
    config_payload["start_date"] = dataset.config.start_date.isoformat()
    manifest = {
        "source": SIMULATION_SOURCE,
        "data_classification": DATA_CLASSIFICATION,
        "is_synthetic": True,
        "warning": "DADOS SINTÉTICOS PARA TESTES; NÃO SÃO OBSERVAÇÕES REAIS OU PÚBLICAS.",
        "generator_version": GENERATOR_VERSION,
        "config": config_payload,
        "counts": dataset.counts,
        "sha256": checksums,
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target
