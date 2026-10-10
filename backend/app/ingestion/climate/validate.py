import re
from datetime import date
from decimal import Decimal, InvalidOperation


def selection(station, start, end):
    if not re.fullmatch(r"A\d{3}", station or ""):
        raise ValueError("Identidade INMET inválida")
    start, end = date.fromisoformat(str(start)), date.fromisoformat(str(end))
    if start > end or (end-start).days > 365 or start.year != end.year or end == date(end.year, 12, 31):
        raise ValueError("Período: até 366 dias no mesmo ano; dia seguinte deve existir no arquivo")
    return start, end


def coordinates(lon, lat):
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("Coordenadas inválidas")


def rainfall(raw):
    if raw.strip() in ("", "-9999", "-9999,0"):
        return None
    try:
        value = Decimal(raw.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Precipitação inválida") from exc
    if not value.is_finite() or not 0 <= value < 10000000 or value != value.quantize(Decimal("0.0001")):
        raise ValueError("Precipitação negativa, não finita ou fora da precisão")
    return value
