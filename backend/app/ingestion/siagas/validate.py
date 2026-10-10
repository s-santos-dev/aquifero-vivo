import math


def coordinates(lon, lat, *, state, bbox=None):
    lon, lat = float(lon), float(lat)
    if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("Coordenadas inválidas")
    # Conservative geographic envelope, not an administrative boundary polygon.
    if state.upper() == "PI" and not (-46.1 <= lon <= -40.3 and -11 <= lat <= -2.5):
        raise ValueError("Coordenadas fora do envelope do Piauí")
    if bbox and not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
        raise ValueError("Coordenadas fora da área selecionada")
    return lon, lat


def number(value):
    if value in (None, ""):
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError("Valor numérico negativo/não finito")
    return result


def selection(state, municipality, bbox, limit):
    if len(state) != 2 or not state.isalpha() or limit < 1:
        raise ValueError("UF/limite inválido")
    if bbox and not (len(bbox) == 4 and all(math.isfinite(v) for v in bbox) and -180 <= bbox[0] < bbox[2] <= 180 and -90 <= bbox[1] < bbox[3] <= 90):
        raise ValueError("BBox inválida: west south east north")
