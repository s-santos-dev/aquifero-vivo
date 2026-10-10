# Relatório da Fase 11 — 10/10/2026

## Resultado e pré-requisito

A Fase 10 estava implementada no checkout, com alterações locais ainda sem commit. Foi verificada antes da integração: **28 testes de cenários aprovados**, incluindo leitura histórica e preservação do banco em schema PostGIS temporário. Não foi feita reversão de alterações locais. Nenhuma fórmula de risco/cenário foi alterada nesta fase.

Fonte utilizada: Serviço Geológico do Brasil, SIAGAS, [FeatureServer/0](https://geoportal.sgb.gov.br/server/rest/services/hidrologia/SIAGAS_MODDAD/FeatureServer/0). Portal, metadados e consulta acessíveis na data da execução. Campos e regras em [siagas-integration.md](siagas-integration.md).

Piloto local Teresina/PI: limite **25**, páginas **10 + 10 + 5**, ordenação por `idt_ponto`, `outSR=4326`. Lote `20261010T162313Z-41e2af8d`, extração em 10/10/2026 às 13:23:13 no fuso America/Fortaleza (16:23:13 UTC).

| Etapa | Resultado |
|---|---|
| Registros consultados no piloto | 25 |
| Normalizados e aceitos | 25 |
| Rejeitados | 0; nenhum motivo de rejeição no piloto |
| Primeira carga | 25 criados, 0 atualizados |
| Segunda carga do mesmo arquivo bruto | 0 criados, 25 atualizados |
| Catálogo final | 105: 80 sintéticos + 25 PUBLIC/SIAGAS |
| Avaliáveis pelo motor na referência 2025-12-30 | 80, todos da demonstração sintética |
| Cadastros SIAGAS | 25 com operação desconhecida; risco insuficiente, score/classificação nulos |
| Setores/vínculos sintéticos | 20 setores e 80 vínculos preservados |
| Medições | 58.400 subterrâneas + 58.400 operacionais + 14.600 chuva = 131.400 |

Checksums MD5 de conteúdo completo ordenado por UUID, calculados antes e depois para cadastros sintéticos, setores, vínculos e três tabelas de medições, são **iguais**. MD5 aqui é um verificador de igualdade de snapshots locais, não uma garantia de autenticidade externa. Evidências: `output/siagas-before.json`, `output/siagas-after.json`, `output/siagas-validation.json`, páginas e manifesto em `data/raw/siagas/<lote>/`, normalizados/relatório em `data/processed/siagas/`. Os dois arquivos de checksum confirmam conteúdo, não somente contagens. As 25 avaliações foram verificadas também pela API HTTP real.

## Arquivos, modelo e contratos

Criados nesta fase:

- `backend/app/ingestion/__init__.py` e `backend/app/ingestion/siagas/{__init__,client,extract,transform,validate,mappings,load,cli}.py`.
- `backend/alembic/versions/0005_siagas_catalog.py`.
- `backend/tests/test_siagas.py`, `backend/tests/test_siagas_database.py`, `backend/tests/fixtures/siagas-teresina.json` e `siagas-metadata.json`.
- `docs/siagas-integration.md`, este relatório e os três arquivos de evidência `output/siagas-*.json`.

Alterados nesta fase: `backend/app/models/domain.py`, `backend/app/schemas/{api,domain}.py`, `backend/app/api/v1.py`, `backend/tests/test_api_v1.py`, `frontend/src/{App,Pages}.tsx`, `frontend/src/styles.css`, `docker-compose.yml`, `README.md`, `docs/architecture.md`. Arquivos locais anteriores de cenário continuam preservados, incluindo `backend/app/scenarios/`, testes, `Simulator.tsx`, documentação e integrações de rota/CORS. Fins de linha dos arquivos modificados foram normalizados para permitir verificação do diff.

Model modificado: `Well`, com identificador externo opcional, metadata JSONB, chave única de origem/ID e status operacional anulável. Migração aditiva `0005`, aplicada ao banco real local e verificada por `alembic check`. Nenhuma tabela de medições/setores/vínculos foi modificada. O único ajuste de contrato existente é aceitar `is_active=null` para desconhecido; booleanos anteriores permanecem. Campos novos são opcionais e filtros/rotas permanecem.

Mapeamento: `idt_ponto` → identidade estável; UF/município → campos existentes; geometria → POINT 4326; profundidade → metros; nome ausente → rótulo explícito SIAGAS; aquífero/situação/uso/NE/ND/datas/atributos → metadata de origem. Situação histórica não determina operação atual; vazão específica permanece m³/h/m, sem converter para vazão produzida. Não há séries novas, demanda, população ou concessionária inventada.

Endpoints utilizados: `/api/v1/wells?source=SIAGAS`, `source=SIMULATED`, `/wells/{id}`, `/wells/{id}/risk`, `/measurements?well_id=...`, `/dashboard/summary`, indicadores e ranking existentes. Frontend: filtro de origem no mapa/lista, marcadores públicos roxos quadrados, legenda, detalhes cadastrais/fonte/datas, aviso de ausência operacional e totais separados na Visão Geral. O público sem séries não abre gráficos operacionais de demonstração.

## Verificações

| Verificação | Resultado |
|---|---|
| Suíte backend completa, `RUN_POSTGIS_TESTS=1` | **155 aprovados** (132 anteriores + 23 SIAGAS) |
| Novos testes após revisão do loader/client | **23 aprovados** |
| Migration real e `alembic check` | Aplicada; `No new upgrade operations detected` |
| TypeScript `tsc --noEmit` e Vite | Aprovados pelo comando `npm run build` |
| `docker compose config --quiet` | Aprovado |
| `git diff --check` | Aprovado após normalizar fins de linha |
| Fonte oficial e paginação real | 3 páginas oficiais gravadas, 25 registros válidos |
| API HTTP real | 105 totais; 25 SIAGAS; 80 simulados; 25 scores nulos |
| Idempotência real | Repetição sem nova consulta: zero duplicatas |
| Preservação do dataset real local | Checksums integrais iguais antes/depois |
| Interface com API real | Validada interativamente: origem, mapa, popup, detalhes e totais |

Dois avisos de depreciação já existentes no conjunto de testes (Starlette/httpx e anyio); não houve falha de teste. Não há lint ou suíte automatizada de frontend configurados.

Testes unitários usam fixture oficial pequena, sem dependência de rede. Cobrem campos ausentes, números inválidos, geometrias nulas/fora da área/invertidas, SRID desconhecido e conversão Web Mercator, unidades, IDs, duplicatas, paginação/limites/repetição de página, indisponibilidade/403/erro JSON e arquivo CSV/GeoJSON. Testes PostGIS em schema temporário com rollback comparam o conteúdo do dataset sintético, fazem duas cargas, verificam fonte/UUID/SRID, filtros e risco nulo, e recusam conflitos com origem alheia/sintética/classificação incorreta.

Na validação visual foi observado cache do servidor Vite após edição de arquivos no volume Docker do Windows: o código novo estava montado e compilava, mas a sessão servia módulo anterior. O frontend foi reiniciado e a navegação recarregada; os controles de origem e estados SIAGAS passaram a aparecer corretamente. Não restou falha funcional conhecida.

## Limitações e próximos passos

Validação **local**, com dados oficiais reais; não representa deployment ou validação operacional em produção. Cadastro histórico não assegura situação atual; data de cadastro não é data de teste nem última atualização. Não há séries suficientes para avaliar operacionalmente os poços SIAGAS. O envelope do Piauí não substitui malha oficial. Licença específica de redistribuição e quotas por tempo não constavam nos metadados examinados; preserve atribuição e confira condições antes de distribuição/ampliação em escala.

RIMAS e clima permanecem planejados. Próximos passos: revisar identidade/estações e unidades de séries reais; registrar qualidade e proveniência por observação; definir associação espacial/temporal verificável; avaliar licenças e cobertura antes de alimentar indicadores. Nenhum módulo RIMAS, satélite, ML, previsão de colapso, concessionária ou financeiro foi implementado.
