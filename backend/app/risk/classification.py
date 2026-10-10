from app.risk.config import CLASSIFICATION_LIMITS


def classify(score: float | None) -> str | None:
    if score is None:
        return None
    return next(label for threshold, label in CLASSIFICATION_LIMITS if score >= threshold)
