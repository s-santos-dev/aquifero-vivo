"""Read-only official ArcGIS client with bounded retries and pagination."""
import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .mappings import URL

log = logging.getLogger(__name__)


class SourceError(RuntimeError):
    pass


class Client:
    def __init__(self, timeout=30, retries=2, pause=0.25, base_url=URL):
        self.timeout, self.retries, self.pause = timeout, retries, pause
        self.base_url = base_url

    def get(self, path="", **params):
        request = Request(self.base_url + path + "?" + urlencode({"f": "json", **params}), headers={"User-Agent": "AquiferoVivo-SIAGAS/1.0"})
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    data = json.load(response)
                if not isinstance(data, dict):
                    raise SourceError("Resposta JSON inválida; objeto esperado")
                if "error" in data:
                    raise SourceError(f"ArcGIS: {data['error']}")
                return data
            except HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504):
                    raise SourceError(f"HTTP {exc.code}; acesso não contornado") from exc
                error = exc
            except (URLError, TimeoutError, OSError, ValueError) as exc:
                error = exc
            if attempt == self.retries:
                raise SourceError(f"Fonte indisponível após {attempt + 1} tentativas: {error}") from error
            delay = 2 ** attempt
            if isinstance(error, HTTPError) and error.headers.get("Retry-After"):
                try:
                    delay = max(delay, int(error.headers["Retry-After"]))
                except ValueError:
                    pass
                if delay > 60:
                    raise SourceError("Fonte pediu espera longa; repita a importação posteriormente") from error
            log.warning("Tentativa %s falhou; aguardando %ss", attempt + 1, delay)
            time.sleep(delay)

    def pages(self, metadata, *, state="PI", municipality=None, bbox=None, limit=25, page_size=100):
        if limit < 1 or page_size < 1:
            raise ValueError("Limite e página devem ser positivos")
        fields = {f["name"] for f in metadata.get("fields", [])}
        oid = metadata.get("objectIdField")
        if not {"str_uf", "str_municipio", "idt_ponto", oid} <= fields:
            raise SourceError("Contrato da fonte mudou; revise o mapeamento")
        if not metadata.get("advancedQueryCapabilities", {}).get("supportsPagination"):
            raise SourceError("Fonte sem paginação confirmada; utilize arquivo oficial")
        quote = lambda value: "'" + value.replace("'", "''") + "'"
        where = "UPPER(str_uf)=" + quote(state.upper())
        if municipality:
            where += " AND UPPER(str_municipio)=" + quote(municipality.upper())
        params = dict(where=where, outFields="*", outSR=4326, returnGeometry="true", orderByFields=oid)
        if bbox:
            params.update(geometry=",".join(map(str, bbox)), geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects")
        offset, seen = 0, set()
        size = min(page_size, int(metadata["maxRecordCount"]))
        if size < 1:
            raise SourceError("Limite de página inválido na fonte")
        while offset < limit:
            data = self.get("/query", **params, resultOffset=offset, resultRecordCount=min(size, limit-offset))
            if data.get("geometryType") != "esriGeometryPoint" or not isinstance(data.get("features"), list):
                raise SourceError("Resposta inválida da fonte")
            features = data["features"]
            if len(features) > min(size, limit-offset):
                raise SourceError("Fonte ignorou limite solicitado")
            ids = [f.get("attributes", {}).get(oid) for f in features]
            if any(i in seen or i is None for i in ids) or len(set(ids)) != len(ids):
                raise SourceError("Paginação repetida/identificadores inválidos; extração interrompida")
            seen.update(ids)
            yield data
            offset += len(features)
            if not data.get("exceededTransferLimit"):
                break
            if not features:
                raise SourceError("Página vazia com limite excedido")
            time.sleep(self.pause)
