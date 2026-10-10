"""Normalize registry descriptors, never generate operational observations."""
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5
from .mappings import SOURCE, URL, FIELDS, UNITS
from .validate import coordinates, number, selection


def text(value):
    return str(value).strip() if value is not None and str(value).strip() else None


def transform(envelope):
    chosen = envelope["selection"]
    state, municipality, bbox, limit = (chosen.get(k) for k in ("state", "municipality", "bbox", "limit"))
    state, limit = state or "PI", limit or 25
    selection(state, municipality, bbox, limit)
    extracted = datetime.fromisoformat(envelope["extracted_at"])
    if extracted.tzinfo is None:
        raise ValueError("Data de extração exige timezone")
    accepted, rejected, seen = [], [], set()
    consulted = 0
    for page in envelope["pages"]:
        srid = page.get("spatialReference", {}).get("latestWkid", page.get("spatialReference", {}).get("wkid"))
        for feature in page["features"]:
            if consulted >= limit:
                break
            consulted += 1
            attrs = feature.get("attributes", {})
            record_id = text(attrs.get("idt_ponto"))
            try:
                if not record_id or not record_id.isdigit() or len(record_id) > 50:
                    raise ValueError("Identificador oficial ausente/inválido")
                if record_id in seen:
                    raise ValueError("Identificador oficial duplicado no lote")
                seen.add(record_id)
                uf, city = text(attrs.get("str_uf")), text(attrs.get("str_municipio"))
                if not uf or uf.upper() != state.upper() or (municipality and (city or "").casefold() != municipality.casefold()):
                    raise ValueError("Registro fora da UF/município selecionado")
                if text(attrs.get("str_natureza_ponto")) not in (None, "Poço tubular", "Poço escavado", "Poço amazonas"):
                    raise ValueError("Natureza do ponto não corresponde a poço")
                geometry = feature.get("geometry", "missing")
                if geometry is None:
                    raise ValueError("Geometria nula")
                if geometry == "missing":
                    if srid != 4326:
                        raise ValueError("Latitude/longitude exigem SRID 4326")
                    lon, lat = attrs.get("num_longitude_decimal"), attrs.get("num_latitude_decimal")
                else:
                    lon, lat = geometry.get("x"), geometry.get("y")
                    if srid in (3857, 102100, 102113):
                        import math
                        x, y = float(lon), float(lat)
                        if not (math.isfinite(x) and math.isfinite(y) and abs(x) <= 20037508.35 and abs(y) <= 20037508.35):
                            raise ValueError("Coordenadas Web Mercator inválidas")
                        lon = math.degrees(x / 6378137)
                        lat = math.degrees(math.atan(math.sinh(y / 6378137)))
                    elif srid != 4326:
                        raise ValueError("SRID não suportado; solicite outSR=4326")
                lon, lat = coordinates(lon, lat, state=state, bbox=bbox)
                depth = number(attrs.get("num_profundidade"))
                if depth is not None and depth >= 100000000:
                    raise ValueError("Profundidade excede capacidade do schema")
                meta = {FIELDS[k]: text(attrs.get(k)) for k in FIELDS}
                warnings = []
                for field, dest in (("ne", "static_level_m"), ("nd", "dynamic_level_m")):
                    try:
                        meta[dest] = number(attrs.get(field))
                    except (ValueError, TypeError):
                        meta[dest] = None
                        warnings.append(f"{field}: valor inválido preservado em attributes")
                if meta["static_level_m"] is not None and meta["dynamic_level_m"] is not None and meta["dynamic_level_m"] < meta["static_level_m"]:
                    meta["static_level_m"] = meta["dynamic_level_m"] = None
                    warnings.append("ND menor que NE; níveis somente nos atributos brutos")
                registered = attrs.get("data_cadastro")
                try:
                    registered = datetime.fromtimestamp(float(registered)/1000, timezone.utc).isoformat() if registered not in (None, "") else None
                except (TypeError, ValueError, OverflowError, OSError):
                    registered = None
                    warnings.append("data_cadastro inválida")
                meta.update(attributes=attrs, units=UNITS, extracted_at=extracted.isoformat(), batch=envelope["batch"], source_url=envelope["source_url"], record_url=f"https://siagasweb.sgb.gov.br/layout/detalhe_poco.php?ponto={record_id}", registered_at=registered, original_updated_at=None, warnings=warnings, operational_status="UNKNOWN")
                accepted.append(dict(id=uuid5(NAMESPACE_URL, "SIAGAS:" + record_id), code="SIAGAS-"+record_id, name=text(attrs.get("str_nome_ponto")) or "SIAGAS " + record_id, municipality=city, state=uf.upper(), depth_m=depth, longitude=lon, latitude=lat, source=SOURCE, data_classification="PUBLIC", source_record_id=record_id, source_metadata=meta, is_active=None))
            except (ValueError, TypeError, AttributeError) as exc:
                rejected.append(dict(source_record_id=record_id, reason=str(exc)))
    return accepted, dict(consulted=consulted, accepted=len(accepted), rejected=rejected, batch=envelope["batch"])
