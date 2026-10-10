from app.risk.service import risk_indicators
from app.scenarios.simulator import simulate


def simulate_well(db, well, request):
    return simulate(risk_indicators(db, well, request.reference_date), well, request)
