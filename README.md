# Aquífero Vivo

Plataforma web experimental para explorar dados de poços e abastecimento, acompanhar indicadores hidroclimáticos, investigar fatores associados a estresse hídrico e comparar cenários. O projeto reúne uma API, uma interface geográfica e um banco espacial. **Não é um sistema operacional de concessionária nem uma ferramenta de previsão hidrogeológica validada.**

## O que o projeto faz

- Apresenta uma visão geral, lista e mapa de poços, setores de abastecimento e detalhes dos registros.
- Consulta históricos de nível subterrâneo, operação e chuva, com origem, classificação, datas e valores ausentes explícitos.
- Calcula indicadores sob demanda e mostra cobertura dos dados e fatores usados por um índice multicritério experimental.
- Ordena poços para investigação, deriva alertas de consulta e sugere verificações para avaliação humana. Essas consultas não gravam avaliações nem enviam notificações.
- Oferece um centro de decisões e uma demonstração guiada, além de um simulador editável que compara parâmetros em horizontes de 30, 60 e 90 dias.
- Importa cadastros públicos SIAGAS/SGB, observações subterrâneas de um piloto RIMAS/SGB e precipitação do INMET. As três integrações preservam a proveniência e são separadas dos dados sintéticos.

## Dados e limites de uso

O banco novo começa vazio: o Compose aplica as migrations, mas **não carrega automaticamente** dados de demonstração nem baixa dados externos. O gerador sintético é explícito e configura, por padrão, 80 poços, 20 setores e 730 dias. Os registros são marcados `SIMULATED`; não representam poços, medições ou operação reais.

As integrações públicas são pilotos com cobertura limitada: SIAGAS fornece cadastro de poços, que não confirma operação atual; RIMAS contém uma série de observações de uma estação; o piloto INMET cobre uma estação e um período definido. Dados brutos e processados de importação ficam em `data/`, diretório local ignorado pelo Git. Consulte os relatórios e as limitações de cada fonte antes de interpretar resultados.

O índice de 0 a 100 usa regras e pesos experimentais; não é probabilidade. O simulador altera indicadores em cópias temporárias e não prevê níveis, vazões, rebaixamento ou falhas futuras. Ausência de dados não significa risco zero ou chuva zero. Não use scores, alertas, recomendações ou cenários para comandar bombeamento, perfurar poços ou tomar decisões reais sem validação técnica independente.

## Componentes

| Diretório | Responsabilidade |
| --- | --- |
| `backend/` | API REST FastAPI, regras de indicadores e risco, simulador, modelos SQLAlchemy, migrations Alembic e importadores |
| `frontend/` | Interface React/TypeScript com Vite, mapa Leaflet e gráficos Recharts |
| `data/` | Arquivos locais brutos, processados e exportações sintéticas; não versionados |
| `docs/` | Arquitetura, modelo, metodologia, integração de fontes, limitações e validações |
| `scripts/` | Utilitários, incluindo geração local de dados sintéticos |
| `output/` | Evidências e relatórios de desenvolvimento |

### Tecnologias e arquitetura

O frontend consulta a API paginada. A API valida contratos com Pydantic e lê/grava PostgreSQL com PostGIS via SQLAlchemy; Alembic gerencia a estrutura do banco. O backend calcula indicadores e risco durante a consulta. O seed e os importadores são comandos separados e explícitos. No Docker Compose, o banco tem volume persistente, a API aplica migrations ao iniciar e a interface usa servidores de desenvolvimento.

```text
Navegador (React, Leaflet, Recharts)
                 │ HTTP
                 ▼
          API FastAPI
                 │ SQLAlchemy / GeoAlchemy
                 ▼
         PostgreSQL + PostGIS

Gerador sintético e importadores SIAGAS, RIMAS e INMET
                 └── validação e carga explícitas no banco
```

Não há modelo de machine learning implementado. O frontend não tem suíte própria de testes ou lint configurados; o build valida TypeScript e empacota com Vite.

## Executar localmente com Docker

Requisitos: Docker Desktop/Engine com suporte a contêineres Linux e Docker Compose v2.

Na raiz do repositório, crie a configuração local e inicie os serviços:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

No Linux/macOS, use `cp .env.example .env`. Se já existir `.env`, mantenha suas credenciais e ajuste apenas o que precisar. Após os serviços ficarem saudáveis, gere a carga sintética padrão, se quiser usar o ambiente de demonstração:

```sh
docker compose exec backend python -m app.simulation.seed_database --scenario NORMAL
```

O comando acima grava os dados no banco local. Para somente gerar e validar sem acessar o banco, acrescente `--dry-run`. Para exportar CSVs, acrescente `--export`. O cenário pode ser `NORMAL`, `DROUGHT` ou `SEVERE_STRESS`; consulte [docs/synthetic-data.md](docs/synthetic-data.md) para opções e política de reset.

Endereços padrão:

- Interface: [http://localhost:5173](http://localhost:5173)
- Saúde da API: [http://localhost:8000/health](http://localhost:8000/health)
- Swagger/OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- PostgreSQL: `localhost:5432`

`/health` confirma que o processo da API responde; não verifica o banco. O serviço do banco tem healthcheck próprio no Compose. `docker compose down` mantém os dados no volume `postgres_data`; `docker compose down -v` também apaga esse volume.

## Páginas da interface

| Rota | Conteúdo |
| --- | --- |
| `/decisions` | Centro de decisões, filtros, ranking, fontes e explicações |
| `/demo/decisao` | Demonstração guiada de decisão preventiva |
| `/dashboard` | Visão geral dos dados disponíveis |
| `/map` | Mapa e filtros geográficos de poços |
| `/wells` e `/wells/:id` | Catálogo e detalhes, indicadores, risco e histórico aplicável |
| `/sectors` e `/sectors/:id` | Setores, poços associados e indicadores agregados |
| `/simulator` | Simulação exploratória de cenários |
| `/alerts` | Alertas derivados para investigação |

## API

Todos os endpoints de aplicação ficam sob `/api/v1`. A documentação interativa em `/docs` é a referência do contrato completo.

| Grupo | Rotas principais | Uso |
| --- | --- | --- |
| Catálogo | `GET /wells`, `/wells/{id}`, `/sectors`, `/sectors/{id}` | Buscar poços e setores; coleções são paginadas |
| Mediçōes | `GET /measurements` | Consultar medições por tipo, entidade, data, classificação e origem |
| Indicadores | `GET /wells/{id}/indicators`, `/sectors/{id}/indicators` | Calcular métricas para uma data de referência |
| Priorização | `GET /risks/wells`, `/wells/{id}/risk`, `/alerts`, `/wells/{id}/recommendations` | Ranking, explicação, alertas derivados e sugestões |
| Cenários | `GET /scenarios/config`, `POST /scenarios/simulate` | Consultar parâmetros e comparar cenários experimentais |
| Clima | `GET /climate/stations`, `/climate/stations/{id}/rainfall`, `/climate/stations/{id}/indicators`, `/wells/{id}/nearby-climate` | Consultar estações e observações de chuva importadas |

Coleções usam `page` e `page_size` e retornam metadados de paginação. Veja os filtros aceitos no Swagger. A rota de saúde é `/health`, fora do prefixo `/api/v1`.

## Importar fontes públicas

Os comandos abaixo primeiro extraem/validam e só gravam com `--load`. Faça isso apenas depois de iniciar o banco e aplicar as migrations (o Compose já faz a aplicação ao subir o backend). Os argumentos de data e seleção variam por fonte; a documentação vinculada explica formatos, proveniência e restrições.

```sh
# SIAGAS: por padrão, valida sem gravar
docker compose exec -T backend python -m app.ingestion.siagas.cli --municipality Teresina --limit 25
# Adicione --load para persistir os cadastros validados

# RIMAS: informe estação, período e arquivo CSV oficial
docker compose exec -T backend python -m app.ingestion.rimas.cli --station 2200034952 --from 2025-01-01 --to 2025-03-31 --file /data/raw/rimas/observacoes.csv
# Adicione --load para persistir se não houver rejeições

# INMET: obtenha o ZIP histórico oficial e informe estação e período
docker compose exec -T backend python -m app.ingestion.climate.cli --station A237 --from 2025-01-01 --to 2025-03-31 --file /data/raw/climate/2025.zip
# Adicione --load para persistir se os dados forem aceitos
```

Consulte [SIAGAS](docs/siagas-integration.md), [RIMAS](docs/rimas-integration.md) e [INMET](docs/climate-integration.md) para comandos completos, lotes offline, formatos e relatórios dos pilotos.

## Desenvolvimento e configuração

Variáveis principais em `.env.example`:

| Variável | Finalidade |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Banco e credenciais locais |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Endereço usado pelo backend local; Compose define o host como `db` |
| `BACKEND_PORT`, `FRONTEND_PORT` | Portas publicadas localmente |
| `CORS_ORIGINS` | Origens permitidas pela API em formato JSON |
| `VITE_API_URL` | Endereço da API visto pelo navegador |
| `SIMULATION_*` | Seed, tamanho, período e área dos dados sintéticos |

Para executar API e interface fora do Compose, use PostgreSQL/PostGIS no Docker e Python 3.12 e Node.js 22.12 ou mais novos:

```powershell
docker compose up -d db
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -e "./backend[data,dev]"
Set-Location backend
.venv/Scripts/alembic.exe upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

Em outro terminal:

```sh
cd frontend
npm ci
npm run dev
```

No Linux/macOS, substitua `backend/.venv/Scripts/` por `backend/.venv/bin/` e use `python3` para criar o ambiente virtual. Para verificar mudanças localmente:

```sh
docker compose exec backend python -m pytest
docker compose exec frontend npm run build
docker compose exec backend alembic check
```

## Documentação

- [Arquitetura](docs/architecture.md) e [modelo de dados](docs/data-model.md)
- [Indicadores](docs/indicators.md), [metodologia do risco](docs/risk-methodology.md) e [priorização](docs/prioritization.md)
- [Metodologia dos cenários](docs/scenario-methodology.md) e [demonstração de decisão](docs/decision-demo.md)
- [Dados sintéticos](docs/synthetic-data.md)
- Integrações: [SIAGAS](docs/siagas-integration.md), [RIMAS](docs/rimas-integration.md) e [INMET](docs/climate-integration.md)
- [Validação geral](docs/validation.md) e relatórios específicos em `docs/*-validation.md`

