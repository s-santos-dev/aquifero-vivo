# Aquífero Vivo

Plataforma web de inteligência preditiva para análise de risco de estresse hídrico em poços e sistemas de abastecimento.

Esta entrega contém a base do projeto, uma primeira API de consulta, o modelo inicial de persistência hidrogeológica e operacional e um gerador de dados operacionais sintéticos. Não implementa ML, SIAGAS ou motor de risco.

## Estrutura

```text
aquifero-vivo/
├── backend/             # FastAPI, SQLAlchemy, Pydantic, Alembic e testes
├── frontend/            # React, TypeScript, Vite e Tailwind CSS
├── data/
│   ├── raw/
│   ├── processed/
│   └── simulated/
├── notebooks/
├── docs/                # Decisões arquiteturais
├── scripts/             # Verificação SQL do PostGIS
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

TanStack Query consulta poços e setores pela API paginada. React Leaflet exibe os poços e as áreas de atendimento; Recharts permanece disponível para uso futuro. Pandas, GeoPandas, NumPy e Scikit-learn integram o extra Python `data`.

## Executar com Docker (recomendado)

Pré-requisitos: Docker Engine/Docker Desktop em execução com contêineres Linux e Docker Compose v2.

Na raiz, copie as configurações locais:

```powershell
Copy-Item .env.example .env
```

Em Linux/macOS, use `cp .env.example .env`. Em seguida:

```sh
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

- Frontend: http://localhost:5173
- API: http://localhost:8000/health — resposta `{"status":"ok"}`
- OpenAPI/Swagger: http://localhost:8000/docs
- PostgreSQL: `localhost:5432`

### API v1

Os endpoints de coleção aceitam `page` (padrão `1`) e `page_size` (padrão `20`, máximo `100`) e retornam `items`, `total`, `page`, `page_size` e `pages`.

| Endpoint | Filtros |
| --- | --- |
| `GET /api/v1/wells` | `q`, `municipality`, `sector_id`, `state`, `is_active` |
| `GET /api/v1/wells/{id}` | — |
| `GET /api/v1/sectors` | `q` |
| `GET /api/v1/sectors/{id}` | — |
| `GET /api/v1/measurements` | `type`, `well_id`, `sector_id`, `measured_from`, `measured_to`, `classification`, `source` |

`measurements` unifica medições subterrâneas (`groundwater`), operacionais (`operational`) e pluviométricas (`rainfall`), identificadas pelo campo `type`. O filtro `type` pode ser repetido. A especificação OpenAPI está em `http://localhost:8000/openapi.json`, com interfaces Swagger em `/docs` e ReDoc em `/redoc`.

O backend aguarda o banco, executa `alembic upgrade head` e inicia o Uvicorn. A primeira migração habilita PostGIS de forma idempotente e a segunda cria o modelo inicial. O frontend aguarda a API. Código do backend e `frontend/src` têm recarga automática; após alterar dependências ou configuração Vite, reconstrua as imagens.

```sh
docker compose logs -f backend frontend
docker compose exec backend python -m pytest
docker compose exec frontend npm run build
docker compose exec backend alembic current
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT PostGIS_Full_Version();"'
docker compose down
```

O volume `postgres_data` preserva os dados após `down`. As credenciais são de desenvolvimento local; alterá-las no `.env` não modifica um banco já inicializado. Os serviços ficam expostos somente em `127.0.0.1`. Esta configuração usa servidores de desenvolvimento e não é um deployment de produção.

## Executar API e frontend localmente

Pré-requisitos adicionais: Python 3.12 e Node.js 22.12+ com npm. Mantenha o banco em Docker:

```sh
docker compose up -d db
```

Backend, em PowerShell, a partir da raiz:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -e "./backend[data,dev]"
Set-Location backend
.venv/Scripts/alembic.exe upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

Em Linux/macOS, use `python3` para criar o ambiente e substitua `.venv/Scripts/` por `.venv/bin/`. A instalação sem o extra `data` (`.[dev]`) basta para trabalhar na API inicial.

Frontend, em outro terminal:

```sh
cd frontend
npm ci
npm run dev
```

Ambos leem o `.env` da raiz. No Docker, o host do banco é sobrescrito para `db`; localmente é `localhost`.

## Variáveis de ambiente

| Variável | Uso |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Banco e credenciais locais |
| `POSTGRES_HOST` | Host do banco na execução local |
| `POSTGRES_PORT` | Porta local do banco; internamente o Compose usa 5432 |
| `BACKEND_PORT`, `FRONTEND_PORT` | Portas publicadas pelo Compose |
| `CORS_ORIGINS` | Lista JSON de origens autorizadas, por exemplo `["http://localhost:5173"]` |
| `VITE_API_URL` | Endereço da API acessível pelo navegador |

Ao mudar as portas publicadas, ajuste também `CORS_ORIGINS` e `VITE_API_URL`. Na execução sem Docker, ajuste as portas nos comandos de inicialização. Variáveis `VITE_` são públicas e incorporadas ao frontend; nunca devem conter segredos. Reinicie o Vite após mudar o `.env`.

## Verificações locais

```sh
cd backend
python -m pytest
alembic upgrade head --sql
cd ../frontend
npm run build
```

Execute os comandos Python no ambiente virtual instalado. Os testes cobrem `/health`, CORS e os contratos de metadata, geometrias, índices, relacionamentos e schemas. O build verifica TypeScript e gera `frontend/dist`. A geração SQL offline verifica a compilação da migration, mas a execução real exige PostgreSQL/PostGIS.

## Dataset operacional sintético

O gerador cria, por padrão, 80 poços, 20 setores e 730 dias. Há três cenários: `NORMAL`, `DROUGHT` e `SEVERE_STRESS`. Todos os CSVs incluem `data_classification=SIMULATED`, `is_synthetic=true`, cenário, seed e versão do gerador; o manifesto repete o aviso e registra contagens e checksums SHA-256.

```powershell
backend/.venv/Scripts/python.exe scripts/generate_synthetic_dataset.py --scenario NORMAL
backend/.venv/Scripts/python.exe scripts/generate_synthetic_dataset.py --scenario DROUGHT
backend/.venv/Scripts/python.exe scripts/generate_synthetic_dataset.py --scenario SEVERE_STRESS
```

Os arquivos do exportador local são gravados somente sob `data/simulated/<cenario>/`, que permanece ignorado pelo Git. Use `--seed`, `--wells`, `--sectors`, `--days` e `--start-date` para controlar a execução. O gerador exige o extra Python `data` por usar NumPy.

A simulação modela chuva sazonal, recarga com memória, demanda por população, utilização por capacidade, estresse acumulado, rebaixamento, risco e falhas dependentes da carga. Com a mesma seed, os cenários partem das mesmas características e realizações meteorológicas base. Os mesmos schemas internos e endpoints aceitam `REAL`, `PUBLIC` e `SIMULATED`, mantendo a classificação explícita na resposta. O indicador de estresse gerado é somente uma variável demonstrativa da simulação; não é persistido como avaliação do motor de risco. A metodologia, o esquema das saídas e os limites de uso estão em [docs/synthetic-data.md](docs/synthetic-data.md).

`/health` indica que a API responde, sem consultar o banco. O Compose verifica o banco separadamente. Consulte [a arquitetura](docs/architecture.md), [o modelo de dados](docs/data-model.md) e [o registro de validação](docs/validation.md).

Referências de configuração: [Vite](https://vite.dev/guide/), [Tailwind CSS](https://tailwindcss.com/docs/installation/using-vite) e [imagem PostGIS](https://hub.docker.com/r/postgis/postgis/).


## Dados simulados do MVP

### Por que existem dados simulados

O MVP utiliza dados operacionais sintéticos para desenvolvimento e demonstração antes da integração completa com fontes externas e dados operacionais reais. Esses dados **NÃO representam poços reais, medições reais ou registros de concessionárias e NÃO devem ser utilizados para decisões operacionais reais**. As relações chuva–recarga–demanda–bombeamento–rebaixamento são hipóteses do simulador, sem validação hidrogeológica científica.

### Arquitetura

```text
Simulator → Validation → Schemas Pydantic internos → SQLAlchemy
          → PostgreSQL/PostGIS → FastAPI → React / React Leaflet
```

Reutilizamos `backend/app/simulation/`, os models e os endpoints já existentes. Não há tabelas ou API exclusivas de mocks. `generator.py` coordena a geração; `config.py` e `scenarios.py` centralizam configuração; `relationships.py` contém coeficientes e relações; `validate.py` verifica o dataset completo; `normalize.py` converte para os schemas normais; `seed_database.py` persiste. A chuva é gerada por setor/dia e as outras séries por poço/dia. `water_level_m` mantém o contrato existente e representa o nível estático.

### Como configurar

As variáveis estão em `.env.example`; copie para `.env` somente ao configurar um ambiente novo. Não sobrescreva suas credenciais existentes.

```dotenv
DATA_MODE=SIMULATED
SIMULATION_SEED=42
SIMULATION_WELLS=80
SIMULATION_SECTORS=20
SIMULATION_DAYS=730
SIMULATION_SCENARIO=NORMAL
SIMULATION_MIN_LATITUDE=-5.30
SIMULATION_MAX_LATITUDE=-4.90
SIMULATION_MIN_LONGITUDE=-42.95
SIMULATION_MAX_LONGITUDE=-42.60
```

A área padrão é uma caixa de demonstração no Piauí, dividida em faixas por setor, sem correspondência com poços ou áreas reais de atendimento. Os códigos são `SIM-PI-001`, etc.; setores usam `SIM-SEC-001`. Coordenadas GeoJSON estão em **longitude, latitude**, SRID 4326; o Leaflet converte para latitude, longitude. O início padrão é `2024-01-01`, configurável por `--start-date YYYY-MM-DD`. A mesma seed, configuração e versão do gerador reproduzem os valores e UUIDs; timestamps de auditoria do banco refletem cada gravação.

`DATA_MODE` aceita `SIMULATED`, `PUBLIC` e `HYBRID` como configuração preparatória, sem escolher um endpoint diferente ou esconder proveniência. Somente o carregamento `SIMULATED` está implementado; mudar a variável não importa dados públicos.

### Como gerar os dados e escolher o cenário

Na raiz, com o serviço backend disponível, estes comandos geram e validam sem gravar no banco:

```sh
docker compose exec backend python -m app.simulation.seed_database --scenario NORMAL --dry-run
docker compose exec backend python -m app.simulation.seed_database --scenario DROUGHT --dry-run --export
docker compose exec backend python -m app.simulation.seed_database --scenario SEVERE_STRESS --dry-run
```

`--export` grava `wells.csv`, `sectors.csv`, `well_daily.csv`, `sector_daily.csv` e `manifest.json` em `data/simulated/<cenario>/`, via volume Docker. CSVs são opcionais, ignorados pelo Git e não são lidos pela aplicação. O script anterior `scripts/generate_synthetic_dataset.py` continua disponível para exportação local. Use `--wells`, `--sectors`, `--days` e `--seed` para sobrescrever o ambiente.

Os multiplicadores centralizados em `scenarios.py` são:

| Cenário | Chuva | Demanda | Eficiência de recarga | Pressão acumulada | Falhas |
| --- | ---: | ---: | ---: | ---: | ---: |
| NORMAL | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| DROUGHT | 0,52 | 1,12 | 0,82 | 1,28 | 1,55 |
| SEVERE_STRESS | 0,24 | 1,28 | 0,62 | 1,72 | 2,30 |

### Como popular o banco e iniciar o sistema

Na raiz, com Docker Desktop em execução:

```sh
docker compose up -d db
docker compose build
docker compose up --no-build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.simulation.seed_database --scenario NORMAL --reset
```

O Compose inicia FastAPI e frontend, e aplica migrations antes da API. Para persistir outro cenário, remova `--dry-run` dos comandos de geração. A geração e carga completas podem levar alguns minutos conforme CPU, memória e armazenamento do ambiente Docker. O seed padrão grava/atualiza 80 poços, 20 setores, 80 vínculos, 58.400 medições subterrâneas, 58.400 operacionais e 14.600 pluviométricas em uma transação. Ele exibe contagens de **registros processados por upsert**, não somente novos inserts.

### Como verificar

- Frontend/mapa: [http://localhost:5173](http://localhost:5173).
- Saúde da API: [http://localhost:8000/health](http://localhost:8000/health).
- Poços: [GET /api/v1/wells?page_size=100](http://localhost:8000/api/v1/wells?page_size=100).
- Detalhe: `GET /api/v1/wells/{id}` com UUID retornado na coleção.
- Setores: [GET /api/v1/sectors](http://localhost:8000/api/v1/sectors).
- Séries: [GET /api/v1/measurements?classification=SIMULATED](http://localhost:8000/api/v1/measurements?classification=SIMULATED).
- Contratos: [Swagger](http://localhost:8000/docs).

O mapa já busca todas as páginas, aplica filtros e desenha geometrias da API. A alteração visual limita-se ao aviso de dados sintéticos e à identificação no popup.

### Como identificar dados simulados

Nos cadastros e respostas da API: `data_classification="SIMULATED"`, `is_synthetic=true` e `source="SIMULATED:AQUIFERO_VIVO"`. `is_synthetic` é derivado da classificação para não permitir flags contraditórias. CSVs também trazem seed, cenário e versão; a configuração da execução exportada está no manifesto. Cadastros legados sem origem conhecida ficam `UNKNOWN`, nunca classificados automaticamente como reais. A migration `0004` adiciona proveniência a poços, setores e vínculos e campos complementares às medições.

### Como limpar/recriar dados simulados

Sem `--reset`, UUIDs estáveis fazem upsert por entidade/data: repetir a configuração não duplica registros; trocar cenário/seed atualiza as mesmas identidades. Janelas antigas e cadastros adicionais permanecem se a configuração diminuir.

Com `--reset`, apenas medições com **ambos** `data_classification=SIMULATED` e `source=SIMULATED:AQUIFERO_VIVO` são removidas antes da regeneração. Ao reduzir a quantidade de poços, o seed também remove cadastros excedentes apenas quando eles e seus vínculos pertencem exclusivamente ao simulador; qualquer relacionamento de outra origem preserva o cadastro, evitando cascatas sobre dados públicos. Registros reais/públicos, de origem desconhecida ou de outros simuladores **não são apagados**. Colisões de UUID/código com outra origem abortam a transação inteira, inclusive o reset. Um lock transacional serializa seeds concorrentes.

### Testes

```sh
docker compose exec -e RUN_POSTGIS_TESTS=1 backend python -m pytest -q -o cache_dir=/tmp/aquifero-pytest-cache
docker compose exec backend alembic check
docker compose exec frontend npm run build
docker compose config --quiet
```

Os testes de banco usam schema isolado em uma transação revertida ao final. Sem `RUN_POSTGIS_TESTS=1`, esses testes são explicitamente pulados. A suíte cobre determinismo, validação, proveniência, ordenação dos cenários, PostGIS, API, idempotência, proteção de dados e rollback em colisões. O frontend não possui suíte de testes ou lint configurados; `build` executa TypeScript e Vite. O backend não possui lint/formatter configurados. Veja [documentação dos campos](docs/synthetic-data.md).

## Integração futura com SIAGAS

```text
SIAGAS → Extract → Transform → Validate → Schema interno → PostgreSQL/PostGIS
```

A integração SIAGAS **ainda não existe**. O próximo passo será criar um adaptador de extração e normalização com proveniência pública, validação de coordenadas/unidades, identificadores externos e política de atualização. Ele reutilizará os schemas internos e models já usados pelo simulador. O objetivo é adicionar/substituir a origem sem alterar frontend, contratos principais da API ou o futuro motor de risco. Esta entrega não implementa ML nem um motor de risco.
