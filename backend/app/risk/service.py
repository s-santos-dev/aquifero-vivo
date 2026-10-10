from app.indicators.service import well_indicators
from app.risk.scoring import evaluate
from app.models import ServiceSector


def risk_indicators(db, well, reference_date):
    indicators = well_indicators(db, well, reference_date)
    if indicators and indicators.sector_id:
        sector = db.get(ServiceSector, indicators.sector_id)
        if sector is None or (sector.data_classification, sector.source) != (well.data_classification, well.source):
            indicators = indicators.model_copy(update={"rainfall": {}})
    return indicators


def well_risk(db, well, reference_date):
    return evaluate(risk_indicators(db, well, reference_date), well.id, well.code, well.data_classification, well.source)
