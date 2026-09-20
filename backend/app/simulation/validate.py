"""Valida integralmente o dataset antes de qualquer escrita no banco."""
from datetime import timedelta
import math
from app.data_provenance import SIMULATION_SOURCE


def validate_dataset(dataset):
    config = dataset.config
    expected_dates = {(config.start_date + timedelta(days=i)).isoformat() for i in range(config.days)}
    wells = {row["well_id"]: row for row in dataset.wells}
    sectors = {row["sector_id"]: row for row in dataset.sectors}

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    require(len(wells) == len(dataset.wells) == config.well_count, "Códigos de poços duplicados ou contagem inválida")
    require(len(sectors) == len(dataset.sectors) == config.sector_count, "Códigos de setores duplicados ou contagem inválida")
    for rows in (dataset.wells, dataset.sectors, dataset.well_daily, dataset.sector_daily):
        for row in rows:
            require(row.get("source") == SIMULATION_SOURCE and row.get("data_classification") == "SIMULATED" and row.get("is_synthetic") is True, "Proveniência SIMULATED obrigatória")
            require(row.get("simulation_seed") == config.seed and row.get("scenario") == config.scenario.value, "Configuração divergente")
            for value in row.values():
                if isinstance(value, float):
                    require(math.isfinite(value), "Valores não finitos")
    for row in [*dataset.wells, *dataset.sectors]:
        require(config.min_latitude <= row["latitude"] <= config.max_latitude, "Latitude inválida")
        require(config.min_longitude <= row["longitude"] <= config.max_longitude, "Longitude inválida")
    for row in dataset.wells:
        require(row["well_id"].startswith("SIM-PI-"), "Código artificial obrigatório")
        require(row["depth_m"] > 0 and row["nominal_flow_m3_h"] >= 0, "Profundidade/vazão inválida")
        require(row["sector_id"] in sectors, "Setor inexistente")
        sector = sectors[row["sector_id"]]
        require(sector["west"] - 1e-6 <= row["longitude"] <= sector["east"] + 1e-6, "Poço fora do setor")
    for row in dataset.sectors:
        require(config.min_longitude <= row["west"] < row["east"] <= config.max_longitude + 1e-9, "Limites do setor inválidos")
        require(config.min_latitude <= row["south"] < row["north"] <= config.max_latitude, "Limites do setor inválidos")

    seen = set()
    for row in dataset.well_daily:
        key = (row["well_id"], row["date"])
        require(key not in seen and key[0] in wells and key[1] in expected_dates, "Série de poço inválida/duplicada")
        seen.add(key)
        require(row["sector_id"] == wells[key[0]]["sector_id"], "Relacionamento inválido")
        require(0 <= row["static_level_m"] <= row["dynamic_level_m"] < wells[key[0]]["depth_m"], "Níveis impossíveis")
        for name in ("flow_rate_m3_h", "pumped_volume_m3", "daily_demand_m3", "utilization"):
            require(row[name] >= 0, f"{name} negativo")
        require(0 <= row["runtime_hours"] <= 24, "Horas fora de 0..24")
        # Tolerance covers independent CSV rounding of flow and runtime to 3 decimals.
        require(abs(row["pumped_volume_m3"] - row["flow_rate_m3_h"] * row["runtime_hours"]) <= 0.1, "Volume incompatível com vazão/horas")
        require(row["operational_failure"] == (row["operating_status"] == "FAILED"), "Falha/status incompatíveis")
    require(len(seen) == config.well_count * config.days, "Série de poço incompleta")
    seen = set()
    for row in dataset.sector_daily:
        key = (row["sector_id"], row["date"])
        require(key not in seen and key[0] in sectors and key[1] in expected_dates, "Série de setor inválida/duplicada")
        seen.add(key)
        require(row["precipitation_mm"] >= 0 and row["daily_demand_m3"] >= 0, "Chuva/demanda negativa")
    require(len(seen) == config.sector_count * config.days, "Série de setor incompleta")
    return dataset
