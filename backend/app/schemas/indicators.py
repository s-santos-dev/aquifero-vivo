from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class IndicatorValue(BaseModel):
    value: float | None
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    unit: str
    observed_days: int = Field(ge=0)
    required_days: int = Field(ge=1)


class IndicatorResponse(BaseModel):
    entity_id: uuid.UUID
    reference_date: date
    data_classification: str
    source: str | None
    sector_id: uuid.UUID | None = None
    groundwater: dict[str, IndicatorValue] = Field(default_factory=dict)
    rainfall: dict[str, IndicatorValue] = Field(default_factory=dict)
    operations: dict[str, IndicatorValue] = Field(default_factory=dict)
    aggregation: dict[str, IndicatorValue] = Field(default_factory=dict)
