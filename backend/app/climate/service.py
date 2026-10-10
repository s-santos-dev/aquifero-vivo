from datetime import datetime, timedelta, timezone
from decimal import Decimal

DAILY_RULE = "INMET_PREVIOUS_HOUR_24_INTERVALS_UTC_V1"


def field(row, key):
    return row[key] if isinstance(row, dict) else getattr(row, key)


def daily_series(rows, start, end):
    indexed = {}
    for row in rows:
        stamp = field(row, "measured_at").astimezone(timezone.utc)
        indexed.setdefault(stamp, []).append(row)
    result = []
    for offset in range((end-start).days+1):
        day = start + timedelta(days=offset)
        begin = datetime.combine(day, datetime.min.time(), timezone.utc)
        intervals = [indexed.get(begin+timedelta(hours=h), []) for h in range(1,25)]
        valid = [items[0] for items in intervals if len(items) == 1 and field(items[0], "availability") == "OBSERVED" and field(items[0], "value_mm") is not None]
        complete = len(valid) == 24
        result.append(dict(date=day.isoformat(), value_mm=str(sum((field(r, "value_mm") for r in valid), Decimal(0))) if complete else None,
            unit="mm", availability="COMPLETE" if complete else "INSUFFICIENT_DATA", observed_hours=len(valid), expected_hours=24,
            missing_hours=sum(len(items)==0 or (len(items)==1 and field(items[0], "availability")=="MISSING") for items in intervals),
            ambiguous_hours=sum(len(items)>1 for items in intervals), timezone="UTC", aggregation_rule=DAILY_RULE,
            quality_status="NOT_PROVIDED", contributor_ids=[str(field(r, "id")) for r in valid]))
    return result


def accumulations(daily, reference):
    indexed = {r["date"]: r for r in daily}
    result = {}
    for window in (7,30,60,90):
        days = [indexed.get((reference-timedelta(days=i)).isoformat()) for i in range(window)]
        sufficient = all(d and d["availability"] == "COMPLETE" for d in days)
        result[str(window)] = dict(value_mm=str(sum((Decimal(d["value_mm"]) for d in days), Decimal(0))) if sufficient else None,
            status="AVAILABLE" if sufficient else "INSUFFICIENT_DATA", expected_days=window,
            complete_days=sum(bool(d and d["availability"]=="COMPLETE") for d in days), unit="mm", quality_status="NOT_PROVIDED")
    return result
