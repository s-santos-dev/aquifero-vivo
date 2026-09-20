# Validação da estrutura inicial

Executada em 20/09/2026, em Windows, com Python 3.12 e Node.js 24.19.0.

| Verificação | Resultado |
| --- | --- |
| Instalação Python `pip install -e "./backend[data,dev]"` | Concluída, incluindo bibliotecas de dados |
| `python -m pytest` (backend) | 9 testes aprovados: saúde, CORS e contratos do modelo |
| `python -m pip check` | Nenhum conflito de dependências |
| Importação de Pandas, GeoPandas, NumPy e Scikit-learn | Aprovada |
| `python -m alembic upgrade head --sql` | Cadeia `0001` + `0002` gerada integralmente |
| `python -m alembic upgrade head` | Aplicada em PostgreSQL 18/PostGIS 3.5; revisão `0002 (head)` |
| `python -m alembic check` | Nenhuma operação de upgrade pendente |
| `npm install` (frontend) | 130 pacotes instalados; auditoria reportou 0 vulnerabilidades |
| `npm run build` | TypeScript e build de produção Vite aprovados |
| Lockfile do frontend | Dependências consistentes com `package.json` |
| Leitura do Compose com PyYAML | Sintaxe YAML válida e três serviços presentes |

## Limitações e problemas encontrados

- Docker não está disponível neste ambiente, portanto os builds e a inicialização via Compose não foram repetidos. A migration foi executada contra a instalação PostgreSQL/PostGIS local e as nove tabelas e os três índices GiST foram inspecionados no banco.
- O npm não estava instalado; uma cópia temporária do npm 10.9.2 foi usada para instalar dependências e executar o build.
- A rede do sandbox bloqueou inicialmente as instalações. Os comandos autorizados fora do sandbox concluíram as instalações.
- O primeiro build foi bloqueado por restrição de leitura do esbuild nos diretórios ancestrais. A repetição autorizada fora do sandbox passou sem alterações no código.
- Os testes passaram com dois avisos de depreciação em dependências: uso de HTTPX pelo TestClient do Starlette e alias `anyio.abc.BlockingPortal`. Nenhum aviso foi suprimido.
- Não foi feita validação visual em navegador ou teste ponta a ponta entre frontend, API e PostgreSQL.

Versões das bibliotecas de dados importadas: Pandas 2.3.3, GeoPandas 1.1.4, NumPy 2.5.3 e Scikit-learn 1.9.1. O frontend possui lockfile; as dependências Python estão delimitadas por faixas no `pyproject.toml` e ainda não possuem lockfile completo.

## Validação do gerador sintético

Executada em 20/09/2026, com Python 3.12.14 e NumPy 2.5.3.

| Verificação | Resultado |
| --- | --- |
| `python -m pytest -q` (backend completo) | 18 testes aprovados; 2 avisos de depreciação de dependências |
| `python -m compileall -q app tests` | Aprovada |
| Geração padrão em memória | 200 poços, 20 setores, 14.600 linhas setor/dia e 146.000 linhas poço/dia em aproximadamente 7 s |
| SQL offline do Alembic | Cadeia `0001` + `0002` + `0003` compilada |
| Reprodutibilidade | Duas execuções de teste com a mesma seed produziram estruturas idênticas |
| Ordenação dos cenários | Chuva e recarga diminuíram; demanda, utilização, risco, rebaixamento persistente e falhas aumentaram de `NORMAL` para `DROUGHT` e `SEVERE_STRESS` |
| Proteção de origem | Schemas de observação rejeitaram `SIMULATED`; CSVs e manifesto mantiveram os marcadores sintéticos |

A migration `0003` foi validada por geração SQL offline, mas não aplicada novamente ao PostgreSQL local nesta rodada. Ela interrompe deliberadamente a atualização se houver medições legadas sem classificação.

## Validação da camada sintética integrada — 2026-09-20

- Suíte final: **49 testes passaram**, incluindo PostgreSQL/PostGIS e API com FastAPI TestClient. Comando: `docker compose exec -e RUN_POSTGIS_TESTS=1 backend python -m pytest -q -o cache_dir=/tmp/aquifero-pytest-cache`.
- Os testes de integração criam tabelas em um schema temporário isolado e revertem a transação inteira. Foram verificadas colisões de UUID e código, rollback do reset, preservação de registros PUBLIC/REAL/UNKNOWN e de outro simulador, relações, geometrias e filtros da API.
- Migration `0004` aplicada com Alembic; `alembic current` mostra `0004 (head)`. `alembic check`: nenhuma operação pendente. A cadeia de migrations também foi compilada em SQL offline.
- PostGIS conectado e consultado: versão 3.5.2, PostgreSQL 17.
- Carga completa NORMAL, seed 42, 200 poços, 20 setores, 730 dias realizada e repetida: 200 vínculos, 146.000 medições subterrâneas, 146.000 operacionais e 14.600 pluviométricas. Nenhum dado real foi apagado. O padrão atual do MVP foi reduzido para 80 poços; o próximo reseed seguro atualiza o banco para essa quantidade.
- DROUGHT e SEVERE_STRESS foram gerados e validados também com os tamanhos padrão. CSVs/manifestos opcionais de NORMAL e DROUGHT estão em `data/simulated/`, fora do versionamento.
- Verificação adicional com 40 poços, 4 setores e 730 dias (seed 42): pressão média demonstrativa NORMAL 52,53; DROUGHT 72,76; SEVERE_STRESS 90,00. Não são resultados científicos nem avaliações do motor de risco.
- Consultas HTTP reais: `/health` OK; `/api/v1/wells` retorna 200; `/api/v1/sectors` retorna 20; `/api/v1/measurements?classification=SIMULATED` retorna 306.600. Proveniência exposta como SIMULATED / is_synthetic=true.
- Navegador: mapa existente exibiu 200 poços, 196 ativos e 4 inativos, com aviso de dados sintéticos e sem redesign.
- Build de frontend inclui `tsc --noEmit` e Vite; aprovado. Não existem scripts de teste ou lint no frontend nem configuração de lint/formatter no backend.
- `docker compose config --quiet`, build das imagens e inicialização dos três serviços verificados. Para o build neste host, foi necessário disponibilizar o diretório do Docker Desktop no PATH do processo; não foi alterada a configuração global.

### Avisos e limites do ambiente

Persistem dois avisos de depreciação de dependências de teste (Starlette/httpx e AnyIO BlockingPortal); não foram suprimidos. A tentativa inicial de build local do frontend encontrou executáveis npm ausentes em `node_modules/.bin`; o build completo foi feito no serviço Docker com dependências instaladas por `npm ci`.

O cache padrão do pytest no diretório sincronizado apresentou erro de permissão. Os testes Docker usaram `/tmp/aquifero-pytest-cache`; os testes locais usaram diretórios exclusivos. A revisão automática bloqueou a limpeza desses diretórios locais (`backend/.simulation-pytest-cache` e `backend/.simulation-test-temp-20260920a`), que foram mantidos e ignorados no Git. Não houve alteração de permissões para contornar o bloqueio.

O seed não remove cadastros excedentes ao reduzir a configuração, para evitar cascatas sobre medições públicas. Apenas suas próprias medições SIMULATED são removidas com `--reset`; a transação reverte tudo em caso de colisão/erro.
