"""Geração de dados operacionais explicitamente sintéticos."""

from app.simulation.generator import (
    SCENARIO_PARAMETERS,
    Scenario,
    SimulationConfig,
    SyntheticDataset,
    generate_dataset,
    write_dataset,
)

__all__ = [
    "SCENARIO_PARAMETERS",
    "Scenario",
    "SimulationConfig",
    "SyntheticDataset",
    "generate_dataset",
    "write_dataset",
]
