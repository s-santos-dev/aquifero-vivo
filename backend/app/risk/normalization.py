import math
from app.risk.config import Criterion


def normalize(value: float | None, criterion: Criterion) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    if criterion.high <= criterion.low or criterion.direction not in (-1, 1):
        raise ValueError("Invalid normalization parameters")
    return min(100.0, max(0.0, 100 * (criterion.direction * value - criterion.low) / (criterion.high - criterion.low)))
