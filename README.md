# Aquífero Vivo

## Centro de Decisões Hídricas — entregas A + B

A entrada principal agora é [Centro de Decisões](http://localhost:5173/decisions): **onde investigar, por que investigar e o que considerar fazer**. Reutiliza ranking/mapa e recomendações existentes, com busca, filtros preservados na URL, separação de fontes, modos simples/técnico, dicionário acessível e comparação de períodos compatíveis.

A [Demonstração de Decisão](http://localhost:5173/demo/decisao) tem cinco etapas, parâmetros editáveis para duas alternativas e resumo para copiar/imprimir. Usa o simulador existente, sem gravar decisões ou misturar dados públicos e sintéticos. Com a base pronta, execute `docker compose up -d db backend frontend`, sem seed/reset. Guia, endpoints, arquivos, validação, limitações e roteiro: [docs/decision-center.md](docs/decision-center.md).

## Demonstração — Decisão Preventiva

Registro da implementação anterior; o fluxo e a validação atuais estão em [Centro de Decisões](docs/decision-center.md).

Acesse [a demonstração guiada](http://localhost:5173/demo/decisao) pelo menu **Decisão Preventiva**. O fluxo reutiliza o simulador e o motor existentes: indicadores → cenário editável → fatores → sugestões de investigação → alternativa de demanda → resumo demonstrativo para copiar/imprimir. Inclui acesso separado à RETE/RIMAS e precipitação regional INMET, sem produzir score operacional com essas fontes.

Com o banco preparado, execute `docker compose up -d db backend frontend`; não execute seed/reset. Funciona com a API e o banco locais, sem internet. Relatório, endpoints, arquivos, evidências, limitações e roteiro de três minutos: [docs/decision-demo.md](docs/decision-demo.md).

## Precipitação pública INMET (Fase 13)

Piloto real: **A237/Caxias–MA, 01/01–31/03/2025, 2.160 observações horárias em mm, 90 dias UTC completos, zero rejeições**. A312/Teresina está sem valores de chuva no arquivo consultado. Caxias está a **67,17 km da RETE**: comparação territorial exploratória, sem atribuição da chuva ao poço ou ao risco. As **131.400 medições sintéticas, 91 observações RIMAS, 80 poços sintéticos, 26 SIAGAS, 20 setores e 80 vínculos** foram preservados com checksums.

Nos detalhes da RETE, a seção **Precipitação próxima — dados públicos** apresenta estação, origem, distância, período, cobertura, gráfico Recharts, seleção temporal e dias ausentes. Diários exigem 24 intervalos horários; ausência não vira zero. API paginada em `/api/v1/climate/stations`, `/{id}/rainfall`, `/{id}/indicators` e `/api/v1/wells/{id}/nearby-climate`. Migrations 0007/0008 criam uma estrutura climática independente.

```sh
# ZIP baixado pelo mecanismo normal de https://portal.inmet.gov.br/dadoshistoricos/
docker compose exec -T backend python -m app.ingestion.climate.cli --station A237 --from 2025-01-01 --to 2025-03-31 --file /data/raw/climate/research/2025.zip --load
```

Sem `--load`, apenas preserva e valida. Métodos, investigação de fontes, formatos, regras diárias, comandos de reimportação, exemplos reais, testes e limitações científicas em [docs/climate-integration.md](docs/climate-integration.md).

## Dados públicos SIAGAS/SGB (Fase 11)

Piloto validado localmente em 10/10/2026: **25 poços reais de Teresina/PI**, consultados pelo serviço oficial ArcGIS e persistidos no PostGIS. Reimportação: zero duplicatas. Os **80 poços simulados, 20 setores e 131.400 medições** foram preservados com checksums de conteúdo. Veja comandos, mapeamento, limites e relatório em [docs/siagas-integration.md](docs/siagas-integration.md) e [docs/siagas-validation.md](docs/siagas-validation.md).

No [mapa](http://localhost:5173/map), escolha Origem → Todos os poços, Poços simulados ou Poços públicos SIAGAS. Cadastros públicos usam marcadores roxos quadrados e apresentam fonte, aquífero, profundidade e datas disponíveis nos detalhes. Não há associação automática a setores, séries fictícias ou scores operacionais: `PUBLIC`, `source=SIAGAS`, `is_synthetic=false`, operação desconhecida (`is_active=null`). A API preserva as rotas, acrescenta `source` em `/api/v1/wells` e proveniência cadastral opcional. Clientes devem aceitar status nulo como desconhecido.

```sh
docker compose up -d backend frontend
docker compose exec -T backend python -m app.ingestion.siagas.cli --municipality Teresina --limit 25 --page-size 10 --raw-dir /data/raw/siagas --processed-dir /data/processed/siagas --load
```

Sem `--load`, apenas extrai e valida. A Visão Geral distingue cadastros públicos, simulados e poços avaliáveis. **Cadastro SIAGAS não confirma operação atual nem monitoramento por concessionária.**

## Simulador de Cenários (Fase 10)

Acesse [Simulador de Cenários](http://localhost:5173/simulator) pelo menu lateral. Busque um poço, selecione uma data histórica (ou deixe em branco para a última medição), consulte a referência e ajuste precipitação, demanda e bombeamento entre -100% e +100%. Clique em **Simular** para comparar referência, cenário escolhido, condições favoráveis e estresse severo em 30, 60 e 90 dias. Os presets são demonstrativos e editáveis; **Restaurar parâmetros** retorna os controles a zero e limpa os resultados.

O backend reutiliza o motor multicritério existente sobre cópias temporárias dos indicadores. A progressão é 1/3, 2/3 e 1 da alteração final, com horas limitadas a 24 por dia. O gráfico e a tabela exibem índices e diferenças em pontos; os fatores explicam as mudanças efetivamente calculadas. Ausência de dados e saturação não são transformadas em diferenças fictícias. Nenhuma medição ou avaliação real é gravada.

`GET /api/v1/scenarios/config` expõe limites e presets. Exemplo para `POST /api/v1/scenarios/simulate` (use um UUID existente retornado por `/api/v1/wells`):

```json
{
  "well_id": "b934083e-91c9-515e-b1fb-79319194b61d",
  "reference_date": "2025-12-30",
  "rainfall_change_pct": -20,
  "demand_change_pct": 15,
  "pumping_change_pct": 10,
  "horizons": [30, 60, 90]
}
```

**Os resultados são simulações exploratórias produzidas a partir de indicadores e parâmetros experimentais. Não constituem previsão hidrogeológica validada nem recomendação operacional automática.** Níveis, drawdown, vazão e falhas permanecem constantes; utilização não representa capacidade hidráulica. Veja fórmulas, tratamento de insuficiência, arquitetura e limitações em [docs/scenario-methodology.md](docs/scenario-methodology.md), e resultados dos testes em [docs/scenario-validation.md](docs/scenario-validation.md).

Plataforma web de inteligência hídrica experimental para análise de risco de estresse hídrico em poços e sistemas de abastecimento.

Esta entrega contém a base do projeto, uma primeira API de consulta, o modelo inicial de persistência hidrogeológica e operacional e um gerador de dados operacionais sintéticos. Implementa indicadores e motor multicritério experimental; não implementa ML. A Fase 11 integra cadastros públicos SIAGAS.

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

TanStack Query consulta poços e setores pela API paginada. React Leaflet exibe os poços e as áreas de atendimento; Recharts exibe o histórico de níveis subterrâneos, operação e precipitação. Pandas, GeoPandas, NumPy e Scikit-learn integram o extra Python `data`.

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
| `GET /api/v1/wells` | `q`, `municipality`, `sector_id`, `state`, `is_active`, `source` |
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

`DATA_MODE` aceita `SIMULATED`, `PUBLIC` e `HYBRID` como configuração preparatória, sem escolher um endpoint diferente ou esconder proveniência. O carregamento sintético e a ingestão SIAGAS estão implementados em comandos explícitos; mudar a variável não importa dados.

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

A integração SIAGAS **ainda não existe**. O próximo passo será criar um adaptador de extração e normalização com proveniência pública, validação de coordenadas/unidades, identificadores externos e política de atualização. Ele reutilizará os schemas internos e models já usados pelo simulador. O objetivo é adicionar/substituir a origem sem alterar frontend, contratos principais da API ou o futuro motor de risco. Esta entrega não implementa ML; o motor multicritério experimental está disponível.


## Consulta do histórico na interface

Selecione um poço no mapa ou na lista para abrir o histórico abaixo do mapa. As abas permitem consultar níveis subterrâneos e operação. Selecione um setor no filtro para consultar sua precipitação; a chuva é do setor selecionado, não uma medição individual do poço.

- Períodos de 30, 90, 365 ou 730 dias, contados a partir da última medição disponível de cada tipo e entidade, incluindo o dia final. Datas e horários são apresentados em UTC.
- Indicadores de nível estático/dinâmico, vazão, volume bombeado, demanda diária, horas de bombeamento, utilização e precipitação, com suas unidades. Utilização é convertida da fração armazenada para percentual.
- Gráfico do indicador selecionado e tabela com 20 registros por página, proveniência e falhas operacionais registradas. Valores ausentes aparecem como `—` e não são convertidos em zero.
- Estados de carregamento, ausência de medições e erro com nova tentativa. Ao mudar de entidade, tipo ou período, os dados são consultados novamente e a paginação é reiniciada.

As consultas usam somente `GET /api/v1/measurements`, filtradas por poço ou setor e tipo. Primeiro é consultada a última medição; depois são carregadas as páginas do período escolhido. Nenhum dataset é gerado, gravado ou redefinido por essa funcionalidade. Não há inferência de risco ou previsão; as medições simuladas são identificadas explicitamente.

## Indicadores hidroclimáticos

A API transforma medições diárias armazenadas em indicadores calculados sob demanda. O poço apresenta chuva do setor vinculado na data de referência, níveis estático e dinâmico, drawdown, vazão, demanda, bombeamento, utilização e falhas. O setor apresenta chuva, quantidade de poços e somas diárias de demanda e volume bombeado. As janelas disponíveis são 7, 30, 60 e 90 dias conforme o indicador; diferenças entre períodos podem exigir até 180 dias.

`GET /api/v1/wells/{id}/indicators` e `GET /api/v1/sectors/{id}/indicators` aceitam `reference_date=YYYY-MM-DD` opcional. Sem o parâmetro, a API usa a última data de medição disponível da entidade, e não a data do computador. Todas as consultas terminam na data solicitada; medições futuras são excluídas. Cada resultado contém `value`, `status`, `unit`, `observed_days` e `required_days`. Uma janela incompleta retorna `value: null` e `status: INSUFFICIENT_DATA`, sem confundir ausência com zero.

Exemplo verificado com a carga sintética atual em 21/09/2026: `SIM-PI-001` tem ID `b934083e-91c9-515e-b1fb-79319194b61d`. A consulta `GET http://localhost:8000/api/v1/wells/b934083e-91c9-515e-b1fb-79319194b61d/indicators` retornou `reference_date: "2025-12-30"`, `rainfall.rainfall_30d.value: 100.924` mm, `groundwater.current_static_level.value: 34.591` m e `operations.demand_avg_30d.value: 1419.64223` m³/dia. Com `?reference_date=2025-06-30`, retornou chuva de 30 dias de `161.524` mm e nível estático de `32.245` m. Esses valores descrevem somente a carga local de demonstração e podem mudar após um novo seed.

Na interface, selecione um poço no mapa ou na lista e use a seção **Indicadores** no painel inferior. O campo de data permite consultar uma referência histórica. Indicadores indisponíveis aparecem como “Dados insuficientes”. A metodologia, as fórmulas e as unidades estão em [docs/indicators.md](docs/indicators.md).

## Funcionalidades do MVP

- [x] Visão Geral com totais calculados pela API
- [x] Mapa de poços, filtros e acesso aos detalhes
- [x] Listagem paginada de poços com busca e filtros
- [x] Detalhes do poço, indicadores e histórico por data
- [x] Indicadores hidroclimáticos e operacionais
- [x] Setores e detalhes com indicadores agregados e poços vinculados
- [x] Motor de risco
- [x] Alertas e recomendações determinísticas
- [x] Cenários exploratórios 30/60/90
- [x] Integração cadastral SIAGAS — piloto de 25 poços

## Rotas do frontend

- `/dashboard`
- `/map`
- `/wells`
- `/wells/:id`
- `/sectors`
- `/sectors/:id`

## Limitações metodológicas

O conjunto operacional atual é sintético. Os indicadores são métricas descritivas; o índice multicritério experimental não é uma previsão validada. As janelas de 30/60/90 dias são períodos analíticos retrospectivos, não cenários futuros. O déficit de chuva compara dois períodos consecutivos do próprio histórico; climatologia de longo prazo ainda não foi integrada. Cadastros SIAGAS foram integrados na Fase 11; um piloto de observações RIMAS foi integrado na Fase 12. Fontes climáticas reais permanecem para fases posteriores. Os cadastros públicos sem séries não recebem índices operacionais. Não utilize estes resultados em decisões operacionais reais.

# Fase 8 — Risco multicritério explicável

O endpoint `GET /api/v1/wells/{id}/risk?reference_date=YYYY-MM-DD` calcula sob demanda um índice experimental de 0 a 100, com cinco grupos, cobertura, classificação e fatores rastreáveis. Nos detalhes do poço, a seção **Análise de Risco** acompanha a data UTC dos indicadores. Cobertura mínima: 80%, exigindo estresse subterrâneo válido; dados ausentes não viram risco zero. Não há gravação de avaliações nem alteração do dataset.

Metodologia, pesos, âncoras de normalização, política temporal, limitações e testes: [docs/risk-methodology.md](docs/risk-methodology.md).

**O motor de risco v1 utiliza regras multicritério experimentais e dados sintéticos. Seus resultados não constituem previsão validada de esgotamento de aquíferos, nem devem fundamentar decisões operacionais reais sem calibração e validação adequadas.**


## Fase 9 — Priorização territorial, alertas e recomendações

Implementados: dashboard, mapa, consulta de poços/setores, histórico, indicadores, motor multicritério, ranking territorial, central `/alerts` e recomendações nos detalhes. Todas as avaliações vêm da API. A data selecionada acompanha os links para detalhes e atualiza indicadores, risco e recomendações.

| Endpoint de leitura | Contrato / filtros |
| --- | --- |
| `GET /api/v1/risks/wells` | `reference_date`, `classification`, `sector_id`, `municipality`, `page`, `page_size` |
| `GET /api/v1/alerts` | Os mesmos filtros; alertas derivados sem persistência |
| `GET /api/v1/wells/{id}/recommendations` | `reference_date`; retorna `risk`, `rules_version` e `recommendations` |
| `GET /api/v1/wells/{id}/risk` | Contrato individual preservado; `reference_date` |

Ranking: CRITICAL → HIGH → ATTENTION → NORMAL, scores decrescentes por classe e empate por código/UUID. INSUFFICIENT_DATA aparece ao final como não avaliado, com score/classificação nulos. As coleções retornam paginação e uma referência comum; ranking também retorna distribuição e contagens sobre todos os resultados filtrados, antes da paginação. Sem data, usa a última medição subterrânea/operacional de origem compatível no catálogo. O serviço faz até oito consultas em lote e lê somente 60 dias de medições necessários aos critérios v1. A API individual mantém sua política anterior de data automática por poço.

### Alertas

HIGH e CRITICAL geram alertas de investigação; INSUFFICIENT_DATA gera alerta separado de qualidade de dados. NORMAL e ATTENTION não geram alertas nesta versão. IDs combinam poço, data, versão do risco e tipo. Consultas são somente leitura, não duplicam linhas nem alteram alertas operacionais em consultas históricas. O model `Alert` existente permanece reservado para um ciclo persistido futuro; não há migrations novas.

### Recomendações

Regras `investigation-v1.0.0`, determinísticas e baseadas em evidências AVAILABLE e finitas:

- STATIC_TREND: tendência da profundidade estática em 30 dias > 0 m/dia; conferir medições, histórico e condições de bombeamento.
- RAINFALL_DEFICIT: déficit relativo recente > 0,30; acompanhar medições e avaliar fontes alternativas cadastradas. Não demonstra perda de recarga nem causalidade.
- PUMPING_LOAD: média de horas em 30 dias > 16 h/dia; revisão humana do regime e inspeção. Mede carga média, não aumento persistente.
- DEMAND_PRESSURE: variação relativa de demanda > 0,20; conferir produção/demanda e pressão operacional.
- RECENT_FAILURES: dias com falha em 30 dias > 0; revisar registros e avaliar manutenção preventiva.
- DATA_COVERAGE: avaliação insuficiente; revisar atualização, integridade, unidades e proveniência.

Sugestões podem usar um indicador válido mesmo quando outros grupos impedem o score global; a evidência e a insuficiência permanecem explícitas. Cada regra traz justificativa e valores com unidades. São orientações para avaliação humana; não ordenam alteração de bombeamento, ativação de reserva ou perfuração.

### Limitações científicas e próximas fases

O MVP **não demonstra capacidade preditiva validada**. Índice 0–100 não é probabilidade; cobertura não é confiança preditiva. Dados sintéticos e parâmetros experimentais exigem validação técnica antes de aplicação operacional. Não há snapshots, reconhecimento/encerramento de alertas ou notificações externas. Ranking recalcula sob demanda; escala maior exigirá agregação SQL/cache com invalidação e revisão científica.

Próximas fases: cenários experimentais 30/60/90 dias; SIAGAS; RIMAS; integração climática; validação histórica; avaliação de custo-benefício; camada sanitária mediante dados apropriados; modelos estatísticos/ML após verificar disponibilidade de dados reais.

Consulte [contratos e arquitetura da fase 9](docs/prioritization.md) e [registro de validação](docs/validation.md).


## Fase 12 — séries reais RIMAS/SGB

Piloto operacional: **91 observações oficiais da estação RETE, Teresina/PI (idt_ponto 2200034952), de 01/01/2025 a 31/03/2025**. Foram encontrados 28 cadastros RIMAS no Piauí; uma série foi verificada para o piloto, e as outras 27 não foram avaliadas temporalmente. A aquisição usa a exportação CSV oficial do portal, com arquivos originais, checksum e proveniência preservados.

O banco agora contém **106 poços (80 sintéticos + 26 SIAGAS), 20 setores, 80 vínculos, 131.400 medições sintéticas intactas e 91 observações RIMAS separadas**. A repetição da carga cria zero registros e preserva as observações existentes.

A migration 0006 cria `groundwater_observations`, separada dos insumos de indicadores. As observações preservam data/hora original sem fuso inventado, unidade em metros, sequência e bombeamento. Não há consolidação diária, interpolação ou atribuição automática de nível estático. Referência, fuso e qualidade não confirmados mantêm a série fora dos indicadores e do risco, que retorna dados insuficientes.

Na lista e no mapa, selecione **Estações com série RIMAS** e abra os detalhes de RETE. O histórico real apresenta gráfico de pontos, filtro por data, tabela paginada, bombeamento e origem. Medições anteriores continuam usando seus contratos e fontes. A API existente aceita `GET /api/v1/measurements?type=groundwater&source=RIMAS&well_id=...&measured_from=2025-01-01T00:00:00&measured_to=2025-03-31T23:59:59&page_size=100`; o valor real fica em `observed_level_m`, sem substituir `water_level_m`.

```powershell
# Aquisição + validação, sem escrita por padrão
docker compose exec -T backend python -m app.ingestion.rimas.cli --station 2200034952 --from 2025-01-01 --to 2025-03-31
# Acrescente --load para carga transacional
# Repetir o lote efetivamente preservado, sem acessar a rede
docker compose exec -T backend python -m app.ingestion.rimas.cli --batch /data/raw/rimas/20261010T165320Z-a225b869 --load
```

Validação: 192 testes aprovados incluindo PostGIS, build TypeScript/Vite, Alembic check e Compose config aprovados; conteúdo anterior comparado por SHA-256; série real conferida no navegador. Serviços, cobertura, campos, política temporal, condições de uso, comandos e limitações: [documentação RIMAS](docs/rimas-integration.md). Evidências: [relatório](output/rimas-validation.json), [antes](output/rimas-before.json), [depois](output/rimas-after.json), [captura do histórico](output/rimas-frontend.png).
