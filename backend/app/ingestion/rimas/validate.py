from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from .mappings import EXPORT_URL, REGISTRY_URL


def selection(station, start, end):
    if not isinstance(station, str) or not station.isdigit() or len(station) > 50:
        raise ValueError("idt_ponto inválido")
    start, end = date.fromisoformat(str(start)), date.fromisoformat(str(end))
    if end < start or (end-start).days > 365:
        raise ValueError("Período deve ter entre 1 e 366 dias")
    return start, end


def provenance(meta):
    if meta.get("source_url") != EXPORT_URL or meta.get("registry_url") != REGISTRY_URL:
        raise ValueError("URL oficial/proveniência inválida")
    if datetime.fromisoformat(meta.get("extracted_at", "")).tzinfo is None or not meta.get("batch"):
        raise ValueError("Extração exige lote e timezone")
    if len(meta.get("raw_sha256", "")) != 64:
        raise ValueError("Checksum bruto ausente")


def level(value):
    try:
        v = Decimal(value.strip().replace(",", "."))
    except (InvalidOperation, AttributeError):
        raise ValueError("Nível ausente/inválido") from None
    if not v.is_finite() or abs(v) >= Decimal("100000000") or v.as_tuple().exponent < -4:
        raise ValueError("Nível fora da capacidade de armazenamento")
    # Negative values are preserved: reference/sign convention remains unknown.
    return v
