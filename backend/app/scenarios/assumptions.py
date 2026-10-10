from app.scenarios.config import MAX_HOURS


def apply(indicators, parameters):
    """Only change explicitly modeled recent-window inputs on a deep copy."""
    if indicators is None:
        return None, []
    result = indicators.model_copy(deep=True)
    warnings = []

    def value(section, key):
        item = getattr(result, section).get(key)
        return item.value if item and item.status == "AVAILABLE" else None

    def set_value(section, key, number):
        item = getattr(result, section).get(key)
        if item and item.status == "AVAILABLE" and item.value is not None:
            item.value = number

    rain = 1 + parameters.rainfall_change_pct / 100
    demand = 1 + parameters.demand_change_pct / 100
    pumping = 1 + parameters.pumping_change_pct / 100
    if parameters.rainfall_change_pct:
        recent = value("rainfall", "rainfall_30d")
        previous = value("rainfall", "rainfall_avg_previous_30d")
        if recent is not None:
            set_value("rainfall", "rainfall_30d", max(0, recent * rain))
        deficit = result.rainfall.get("recent_rainfall_deficit_30d")
        if deficit:
            if recent is not None and previous is not None and previous > 0:
                deficit.value = max(0, 1 - recent * rain / (previous * 30))
            else:
                deficit.value = None
                deficit.status = "INSUFFICIENT_DATA"
                warnings.append("Déficit indisponível: faltam janelas de chuva compatíveis ou a chuva anterior é zero.")
    if parameters.demand_change_pct:
        for key in ("demand_avg_30d",):
            original = value("operations", key)
            if original is not None:
                set_value("operations", key, max(0, original * demand))
        pressure = value("operations", "demand_pressure_30d")
        if pressure is not None:
            set_value("operations", "demand_pressure_30d", (1 + pressure) * demand - 1)
    if parameters.pumping_change_pct:
        hours = value("operations", "pumping_hours_avg_30d")
        if hours is not None:
            hypothetical_hours = min(MAX_HOURS, max(0, hours * pumping))
            set_value("operations", "pumping_hours_avg_30d", hypothetical_hours)
            if hours * pumping > MAX_HOURS:
                warnings.append("Horas de bombeamento limitadas a 24 h/dia; pressão solicitada pode permanecer saturada.")
            volume = value("operations", "pumped_volume_avg_30d")
            if volume is not None:
                if hours > 0:
                    set_value("operations", "pumped_volume_avg_30d", max(0, volume * hypothetical_hours / hours))
                elif volume == 0:
                    set_value("operations", "pumped_volume_avg_30d", 0)
                else:
                    warnings.append("Volume preservado: a referência tem volume positivo e horas zero; não há razão operacional definida.")
        utilization = value("operations", "utilization_avg_30d")
        if utilization is not None:
            set_value("operations", "utilization_avg_30d", max(0, utilization * pumping))
    return result, warnings
