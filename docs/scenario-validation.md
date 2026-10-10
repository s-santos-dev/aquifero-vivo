# Validação da Fase 10 — 10/10/2026

## Funcionalidades e arquivos

Implementados: seleção/busca de poço, referência histórica, baseline com indicadores/fatores/proveniência/cobertura, sliders e campos de precipitação/demanda/bombeamento, restauração local, presets editáveis, comparação de cenários favoráveis/selecionados/adversos, gráfico Recharts de 30/60/90 dias, diferenças em pontos, explicações, loading, erros e insuficiência.

Criados: `backend/app/scenarios/{__init__,config,schemas,assumptions,comparison,simulator,service}.py`, `backend/tests/test_scenarios.py`, `backend/tests/test_scenarios_database.py`, `frontend/src/Simulator.tsx`, `docs/scenario-methodology.md` e este relatório.

Modificados: `backend/app/api/v1.py` (rotas), `backend/app/main.py` (CORS POST), `backend/app/risk/service.py` (compartilha obtenção de indicadores com verificação de origem), `frontend/src/{App,Pages}.tsx` (menu/rota), `frontend/src/api.ts` (POST), `frontend/src/styles.css` e `README.md`. Não houve mudança na fórmula do motor, nos modelos ORM ou em migrações.

Endpoints: `POST /api/v1/scenarios/simulate` e `GET /api/v1/scenarios/config`. Percentuais: `rainfall_change_pct`, `demand_change_pct`, `pumping_change_pct`, todos finitos entre -100 e +100; referência opcional e horizontes 30/60/90. Fórmulas e premissas completas em [scenario-methodology.md](scenario-methodology.md).

## Verificações executadas

| Verificação | Resultado |
|---|---|
| Pré-requisito: testes de risco e priorização | 39 aprovados antes da implementação |
| Suíte completa com `RUN_POSTGIS_TESTS=1` | 132 aprovados, incluindo integração PostGIS; 2 avisos de depreciação existentes em Starlette/httpx/anyio |
| Novos testes | 27 testes de unidade/contrato + 1 integração de banco |
| TypeScript e Vite (`npm run build`) | Aprovados |
| FastAPI/contratos/CORS POST | Aprovados por TestClient, com resposta validada por Pydantic |
| `alembic check` | No new upgrade operations detected |
| `docker compose config --quiet` | Aprovado |
| Serviços Docker | Backend e banco saudáveis; frontend em execução |
| `git diff --check` | Aprovado após normalizar fins de linha |
| Lint | Não configurado no projeto |

Testes novos cobrem identidade com zero, determinismo, limites/NaN/infinito, horizontes válidos e únicos, progressão com âncora fixa, fórmulas, não negatividade, teto de horas, saturação, monotonicidade, deltas e soma de contribuições, coerência das explicações, referências, origem incompatível, ausência de dados e denominadores zero. Integração em schema PostGIS temporário verifica conteúdo dos registros antes/depois e altera somente observações futuras da fixture para confirmar exclusão; tudo sofre rollback ao final.

Na primeira execução completa, um teste novo de snapshot falhou porque comparava `repr` de geometrias ORM, que inclui endereço de memória. A comparação foi corrigida para valores serializados estáveis; o teste de integração e a suíte completa passaram. Durante a validação no navegador, as consultas dos presets comparativos enviavam o campo `label`, rejeitado pelo schema estrito: o frontend passou a enviar explicitamente os três parâmetros permitidos. A simulação e a comparação foram revalidadas com sucesso após a correção. Nenhuma falha ficou pendente.

## Validação da interface com API real

Executada em `http://localhost:5173/simulator` no navegador: menu e abertura, busca por SIM-PI-001, seleção, baseline da API em 2025-12-30, preset de estiagem, alteração de slider com teclado e campos numéricos, execução, loading com controles desabilitados, gráfico/tabela, expansão dos fatores, restauração com controles zero/resultados removidos e referência histórica com insuficiência. O estado de erro 422 foi observado durante a correção do contrato dos presets; depois, a mesma operação concluiu normalmente. Não há suíte automatizada de frontend configurada; esta validação foi interativa, complementada pelo build.

Exemplo observado na carga local, com chuva -30%, demanda +20% e bombeamento +10%:

| Horizonte | Referência | Selecionado | Favorável | Estresse severo |
|---|---:|---:|---:|---:|
| 30 dias | 20,28 | 22,96 | 19,30 | 24,30 |
| 60 dias | 20,28 | 25,64 | 18,48 | 31,59 |
| 90 dias | 20,28 | 28,80 | 16,62 | 41,19 |

São valores calculados pela API sobre a carga atual, não mocks. Em 90 dias, o bombeamento permaneceu no subscore 100 por saturação; não foi forçado aumento. Data 2024-02-01 retornou cobertura 60%, índices nulos e diferenças ausentes nos três cenários. Nenhuma data foi tratada como observação futura simulada persistida.

## Demonstração e limites

Abra `/simulator`, selecione SIM-PI-001 com data automática, escolha Estiagem, altere a demanda para +20% e clique Simular. Veja os três horizontes e abra Fatores e hipóteses — 90 dias. Compare com favorável/estresse severo; clique Restaurar parâmetros. Escolha uma data inicial do histórico para demonstrar insuficiência.

Os índices são exploratórios, não previsões validadas nem recomendações automáticas. Níveis, drawdown, vazão e falhas não são inferidos. Cobertura não representa confiança preditiva. Presets e coeficientes não são cenários climáticos oficiais. O simulador não grava medições, alertas, cadastros ou avaliações. A próxima fase recomendada é revisão metodológica por especialistas e definição de calibração/validação com dados reais e proveniência.

Comandos reproduzíveis:

```sh
docker compose exec -T -e RUN_POSTGIS_TESTS=1 backend python -m pytest -q -p no:cacheprovider
docker compose exec -T frontend npm run build
docker compose exec -T backend alembic check
docker compose config --quiet
docker compose ps
```
