"""Vocabulário central de proveniência para impedir mistura de dados."""

from enum import StrEnum


SIMULATION_SOURCE = "SIMULATED:AQUIFERO_VIVO"


class DataClassification(StrEnum):
    REAL = "REAL"
    PUBLIC = "PUBLIC"
    SIMULATED = "SIMULATED"


OBSERVATION_CLASSIFICATIONS = frozenset(
    {DataClassification.REAL, DataClassification.PUBLIC}
)


def require_observation(classification: DataClassification | str) -> DataClassification:
    """Guarda opcional para análises que exigem observações reais; não limita a API."""

    value = DataClassification(classification)
    if value not in OBSERVATION_CLASSIFICATIONS:
        raise ValueError(
            "SIMULATED não pode ser exposto como observação real"
        )
    return value
