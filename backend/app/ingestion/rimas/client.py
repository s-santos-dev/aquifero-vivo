"""Official read-only CSV export, bounded retries; no HTML data extraction."""
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from app.ingestion.siagas.client import Client as ArcGISClient, SourceError
from .mappings import EXPORT_URL, REGISTRY_URL, MAX_BYTES
from .validate import selection


class Client:
    def __init__(self, timeout=30, retries=2):
        self.timeout, self.retries = timeout, retries
        self.registry = ArcGISClient(timeout=timeout, retries=retries, base_url=REGISTRY_URL)

    def station(self, station):
        if not station.isdigit():
            raise ValueError("idt_ponto inválido")
        data = self.registry.get("/query", where=f"idt_ponto={station}",
            outFields="idt_ponto,str_uf,str_municipio,str_nome_ponto,num_profundidade,status_rimas",
            outSR=4326, returnGeometry="true", resultRecordCount=2)
        features = data.get("features", [])
        if data.get("exceededTransferLimit") or len(features) != 1 or str(features[0].get("attributes", {}).get("idt_ponto")) != station:
            raise SourceError("Cadastro oficial ausente/ambíguo")
        if features[0]["attributes"].get("status_rimas") != "Rimas":
            raise SourceError("Estação não confirmada como RIMAS")
        return data

    def export(self, station, start, end):
        start, end = selection(station, start, end)
        params = dict(acao="exportacao", tipoExp="expCsv", grafico="nivelDagua", idponto=station,
            intervaloDataMin=start.strftime("%d/%m/%Y"), intervaloDataMax=end.strftime("%d/%m/%Y"))
        req = Request(EXPORT_URL, data=urlencode(params).encode(), headers={"User-Agent": "AquiferoVivo-RIMAS/1.0"})
        for attempt in range(self.retries+1):
            try:
                with urlopen(req, timeout=self.timeout) as response:
                    headers = dict(response.headers)
                    content = response.read(MAX_BYTES+1)
                if len(content) > MAX_BYTES:
                    raise SourceError("Exportação excede limite do piloto")
                if not content.startswith(b"Id Ponto:;"):
                    raise SourceError("CSV oficial esperado; resposta não interpretada como dados")
                return content, params, headers
            except HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504):
                    raise SourceError(f"HTTP {exc.code}; acesso não contornado") from exc
                error = exc
            except (URLError, TimeoutError, OSError) as exc:
                error = exc
            if attempt == self.retries:
                raise SourceError(f"Fonte indisponível após {attempt+1} tentativas: {error}") from error
            delay = 2**attempt
            if isinstance(error, HTTPError):
                try: delay = max(delay, int(error.headers.get("Retry-After", "0")))
                except ValueError: pass
            if delay > 60:
                raise SourceError("Fonte pediu espera longa; tente posteriormente") from error
            time.sleep(delay)
