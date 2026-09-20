from dataclasses import dataclass
from datetime import date
from app.simulation.scenarios import Scenario

@dataclass(frozen=True)
class SimulationConfig:
    scenario: Scenario = Scenario.NORMAL
    seed: int = 42
    well_count: int = 80
    sector_count: int = 20
    days: int = 730
    start_date: date = date(2024, 1, 1)

    min_latitude: float = -5.30
    max_latitude: float = -4.90
    min_longitude: float = -42.95
    max_longitude: float = -42.60
    region: str = "Área de demonstração PI (sintética)"

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario", Scenario(self.scenario))
        import math
        bounds = (self.min_latitude, self.max_latitude, self.min_longitude, self.max_longitude)
        if not all(math.isfinite(v) for v in bounds):
            raise ValueError("Limites devem ser finitos")
        if not (-90 <= self.min_latitude < self.max_latitude <= 90 and
                -180 <= self.min_longitude < self.max_longitude <= 180):
            raise ValueError("Limites geográficos inválidos")
        if self.seed < 0:
            raise ValueError("seed deve ser não negativa")
        if self.well_count < 1 or self.sector_count < 1 or self.days < 2:
            raise ValueError("well_count e sector_count devem ser positivos; days deve ser >= 2")
        if self.well_count < self.sector_count:
            raise ValueError("well_count deve ser maior ou igual a sector_count")



    @classmethod
    def from_env(cls, **overrides):
        from pydantic_settings import BaseSettings, SettingsConfigDict
        from app.config import Settings

        class Environment(BaseSettings):
            model_config = SettingsConfigDict(
                env_prefix="SIMULATION_", env_file=Settings.model_config["env_file"], extra="ignore"
            )
            seed: int = 42
            wells: int = 80
            sectors: int = 20
            days: int = 730
            scenario: Scenario = Scenario.NORMAL
            min_latitude: float = -5.30
            max_latitude: float = -4.90
            min_longitude: float = -42.95
            max_longitude: float = -42.60
            region: str = "Área de demonstração PI (sintética)"

        values = Environment().model_dump()
        values["well_count"] = values.pop("wells")
        values["sector_count"] = values.pop("sectors")
        values.update({key: value for key, value in overrides.items() if value is not None})
        return cls(**values)
