from statistics import mean
from app.risk.config import GROUPS, MIN_COVERAGE, VERSION
from app.risk.classification import classify
from app.risk.normalization import normalize
from app.risk.explanation import explain
from app.schemas.risk import RiskInput, RiskFactor, RiskResponse


def evaluate(indicators, well_id, well_code, data_classification, source):
    if abs(sum(weight for _, weight, _ in GROUPS.values()) - 1) > 1e-9 or any(weight <= 0 for _, weight, _ in GROUPS.values()):
        raise ValueError("Group weights must be positive and sum to one")
    factors = []
    for group, (name, weight, criteria) in GROUPS.items():
        inputs = []
        for criterion in criteria:
            item = getattr(indicators, criterion.section).get(criterion.key) if indicators else None
            normalized = normalize(item.value, criterion) if item and item.status == "AVAILABLE" else None
            inputs.append(RiskInput(section=criterion.section, indicator=criterion.key,
                                    value=item.value if item else None, unit=item.unit if item else None,
                                    status="AVAILABLE" if normalized is not None else "INSUFFICIENT_DATA", normalized=normalized))
        available = all(item.normalized is not None for item in inputs)
        factors.append(RiskFactor(group=group, name=name, indicators=inputs,
                                  status="AVAILABLE" if available else "INSUFFICIENT_DATA",
                                  subscore=mean(item.normalized for item in inputs) if available else None,
                                  weight=weight, effective_weight=None, contribution=None,
                                  explanation=explain(name, inputs, available)))
    coverage = round(sum(item.weight for item in factors if item.subscore is not None), 10)
    sufficient = coverage >= MIN_COVERAGE and factors[0].subscore is not None
    if sufficient:
        for item in factors:
            if item.subscore is not None:
                item.effective_weight = item.weight / coverage
                item.contribution = item.effective_weight * item.subscore
    score = min(100.0, max(0.0, sum(item.contribution for item in factors if item.contribution is not None))) if sufficient else None
    factors.sort(key=lambda item: (item.contribution is not None, item.contribution or 0), reverse=True)
    return RiskResponse(well_id=well_id, well_code=well_code,
                        reference_date=indicators.reference_date if indicators else None,
                        data_classification=data_classification, source=source, model_version=VERSION,
                        score=score, status="AVAILABLE" if sufficient else "INSUFFICIENT_DATA",
                        classification=classify(score), coverage=coverage, minimum_coverage=MIN_COVERAGE,
                        subscores={item.group: item.subscore for item in factors}, factors=factors,
                        unavailable_groups=[item.group for item in factors if item.subscore is None])
