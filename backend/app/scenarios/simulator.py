from app.risk.scoring import evaluate
from app.risk.recommendations import recommendations
from app.scenarios.assumptions import apply
from app.scenarios.comparison import compare
from app.scenarios.config import VERSION, PROGRESSION, ASSUMPTIONS, WARNINGS
from app.scenarios.schemas import Parameters, HorizonResult, SimulationResponse


def simulate(indicators, well, request):
    def assess(data):
        return evaluate(data, well.id, well.code, well.data_classification, well.source)
    baseline = assess(indicators)
    results = []
    for horizon in request.horizons:
        parameters = Parameters(**{key: getattr(request, key) * PROGRESSION[horizon] for key in Parameters.model_fields})
        temporary, warnings = apply(indicators, parameters)
        risk = assess(temporary)
        delta, relative, factors = compare(baseline, risk)
        results.append(HorizonResult(horizon=horizon, label=f"Índice sob cenário hipotético — {horizon} dias",
                                     applied_parameters=parameters, risk=risk, indicators=temporary,
                                     delta_points=delta, delta_pct=relative, factors=factors, warnings=warnings,
                                     recommendations=recommendations(risk)))
    return SimulationResponse(well_id=well.id, well_code=well.code, reference_date=baseline.reference_date,
                              data_classification=well.data_classification, source=well.source,
                              simulation_version=VERSION, parameters=request, baseline=baseline,
                              baseline_indicators=indicators, results=results, assumptions=ASSUMPTIONS, warnings=WARNINGS)
