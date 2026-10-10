"""Real historical reads and persistent-state protection in a rollback-only schema."""
from datetime import date
from sqlalchemy import select, func
from app.models import Well, GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement, RiskAssessment, Alert
from app.simulation import SimulationConfig, generate_dataset
from app.simulation.seed_database import seed_dataset
from app.scenarios.schemas import SimulationRequest
from app.scenarios.service import simulate_well
from app.risk.service import well_risk
from test_simulation_database import db, pytestmark


def test_historical_scenarios_preserve_all_records(db):
    dataset = generate_dataset(SimulationConfig(well_count=2, sector_count=1, days=100))
    seed_dataset(db, dataset)
    well = db.scalar(select(Well).order_by(Well.code))
    models = [Well, GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement, RiskAssessment, Alert]
    def snapshot():
        return {m.__tablename__: sorted(tuple(str(getattr(row, c.key)) for c in m.__table__.columns) for row in db.scalars(select(m))) for m in models}
    before = snapshot()
    reference = date.fromisoformat(dataset.well_daily[-11]["date"])
    request = SimulationRequest(well_id=well.id, reference_date=reference, rainfall_change_pct=-60, demand_change_pct=30, pumping_change_pct=50)
    response = simulate_well(db, well, request)
    assert response.baseline == well_risk(db, well, reference)
    assert response.baseline.status == "AVAILABLE"
    assert all(r.risk.reference_date == reference for r in response.results)
    db.flush()
    db.expire_all()
    assert snapshot() == before
    # Change only observations after the reference and prove they never enter inputs.
    future = list(db.scalars(select(OperationalMeasurement).where(OperationalMeasurement.well_id == well.id, func.date(OperationalMeasurement.measured_at) > reference)))
    original_demands = [(row, row.daily_demand_m3) for row in future]
    for row, _ in original_demands:
        row.daily_demand_m3 = 999999
    db.flush()
    assert simulate_well(db, well, request) == response
    for row, original in original_demands:
        row.daily_demand_m3 = original
    db.flush()
    db.expire_all()
    assert snapshot() == before
    early = simulate_well(db, well, request.model_copy(update={"reference_date": date.fromisoformat(dataset.well_daily[0]["date"])}))
    assert early.baseline.score is None
