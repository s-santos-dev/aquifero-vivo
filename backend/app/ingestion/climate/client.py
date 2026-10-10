"""Official public download only. Protection/authentication errors stop acquisition."""
import time
import httpx

MAX_BYTES = 150 * 1024 * 1024


def source_url(year):
    if not 2000 <= year <= 2100:
        raise ValueError("Ano inválido")
    return f"https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip"


class Client:
    def __init__(self, client=None):
        self.client = client or httpx.Client(timeout=60, follow_redirects=True)

    def download(self, year, destination):
        url = source_url(year)
        for attempt in range(3):
            try:
                with self.client.stream("GET", url) as response:
                    response.raise_for_status()
                    if not (response.url.host == "inmet.gov.br" or response.url.host.endswith(".inmet.gov.br")):
                        raise ValueError("Redirecionamento para fonte não oficial")
                    size = 0
                    with destination.open("wb") as f:
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > MAX_BYTES:
                                raise ValueError("Arquivo excede limite de 150 MiB")
                            f.write(chunk)
                    if size == 0:
                        raise ValueError("Resposta vazia")
                    return dict(response.headers)
            except httpx.HTTPStatusError as exc:
                # No retry on authentication/protection/rate limits.
                if exc.response.status_code < 500 or attempt == 2:
                    raise
            except httpx.TransportError:
                if attempt == 2:
                    raise
            time.sleep(attempt + 1)
