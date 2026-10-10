# Demonstração — Decisão Preventiva

> Registro da entrega anterior. A versão atual tem cinco etapas e três parâmetros editáveis em ambas as alternativas. Consulte [Centro de Decisões — entregas A + B](decision-center.md) para o fluxo, validação e roteiro atuais.

## Iniciar

Com o banco local já preparado, execute `docker compose up -d db backend frontend` na raiz e abra http://localhost:5173/demo/decisao, ou **Decisão Preventiva** no menu. Não executar seed/reset para apresentar. Se o Docker no Windows não detectar alterações dos arquivos montados, execute `docker compose restart backend frontend`.

O percurso consulta somente serviços locais e dados já importados. Não exige mapas, tiles, fontes externas ou internet. Docker e os serviços precisam estar disponíveis; não há cache que substitua a API desligada.

## Auditoria e reutilização

README, `/simulator`, `Simulator.tsx`, rotas em `backend/app/api/v1.py`, contratos e serviço `app/scenarios/`, motor `app/risk/scoring.py`, recomendações `app/risk/recommendations.py` e painéis RIMAS/INMET foram inspecionados antes da implementação. O catálogo confirma SIM-PI-001 e RETE com observações RIMAS. Há modificações anteriores no workspace relacionadas às integrações públicas; elas foram preservadas.

Não existe segundo motor, segundo simulador, tabela ou migration para a demonstração. O formulário reutiliza os controles extraídos de Simulator, os helpers de API, TanStack Query, os componentes Recharts e as classes visuais existentes. RETE reutiliza RimasHistory, que inclui ClimateHistory. Nenhuma regra de recomendação foi duplicada: cada resultado hipotético chama a função existente `recommendations(risk)` no backend e acrescenta `recommendations` ao contrato de HorizonResult.

## Funcionalidades

1. Seleção inicial por código SIM-PI-001, se disponível; fallback para outro cadastro sintético. Identificação e origem vêm do catálogo. Data vazia usa a última medição do backend; data histórica pode ser editada. Indicadores, índice, classificação e cobertura vêm da referência calculada.
2. Preset editável −30% de precipitação, +20% de demanda e +10% de bombeamento. São hipóteses de entrada, não resultados fixos. Limites vêm de config; horizontes de 30/60/90 dias usam progressão existente de 1/3, 2/3 e 1.
3. Gráfico de índices, diferença em pontos, subscores, contribuições à variação, cobertura e aviso quando a classificação mudar. Valores insuficientes permanecem sem índice. Saturação é explicada pelo backend.
4. Sugestões geradas pelas regras já existentes, com regra/fator, indicador e valor hipotético, justificativa e investigação proposta. Evidências pequenas preservam até seis casas decimais para não mostrar uma tendência positiva como zero.
5. Alternativa com demanda editável (inicialmente −10%), mantendo precipitação, bombeamento, referência e horizontes. Controles dos parâmetros mantidos estão desabilitados. Exibe índice e diferença em pontos ante o cenário.
6. Resumo demonstrativo com fatores, recomendações, parâmetros solicitados/aplicados, alternativa calculada, justificativa livre, proveniência e limitações. Copiar usa Clipboard API com seleção do texto como fallback. Imprimir usa `window.print()` e CSS para exibir o resumo completo, removendo navegação e formulário. Justificativa permanece somente no estado React.

Há navegação com etapa ativa, bloqueio de resultados antes da simulação ou depois de editar parâmetros, estados de carregamento/erro e reinício. O acesso público só aparece para RETE não sintética com observações cadastradas. Não recomenda ativação de reserva nem emite ordem de serviço.

## Endpoints

- `GET /api/v1/wells`, paginado: catálogo, proveniência e existência de RETE.
- `GET /api/v1/scenarios/config`: limites e versão do simulador.
- `POST /api/v1/scenarios/simulate`: referência com parâmetros zero, cenário e alternativa; resultados e recomendações calculados, sem persistência.
- `GET /api/v1/measurements?type=groundwater&source=RIMAS&well_id=...`: histórico real.
- `GET /api/v1/wells/{id}/nearby-climate`: estações importadas próximas e distância geodésica.
- `GET /api/v1/climate/stations/{id}/rainfall`: histórico climático regional.

O endpoint individual de recomendações continua preservado para outros fluxos. Nesta demonstração, usar apenas esse endpoint histórico para o cenário produziria recomendações da referência; por isso as regras existentes são aplicadas diretamente ao risco hipotético no endpoint de simulação.

## Validação em 10/10/2026

- Suite backend completa com `RUN_POSTGIS_TESTS=1`: **235 aprovados**, incluindo simulador, recomendações e preservação transacional dos registros. Avisos de depreciação do TestClient e de permissão para cache pytest não afetam resultados.
- Build TypeScript/Vite aprovado após os ajustes de contrato/frontend.
- Contrato OpenAPI real confirma array de Recommendation em HorizonResult; teste de API confere igualdade com o retorno das regras existentes. Parâmetros inválidos seguem retornando 422.
- `docker compose config --quiet` e `alembic check` aprovados; nenhuma alteração de schema necessária.
- Fluxo no navegador com API real: seleção inicial, preset, resultado, fatores, recomendações, comparação, justificativa e cópia do resumo. Também verificados histórico RETE e precipitação regional INMET.
- O botão de impressão acionou o diálogo nativo, que bloqueou comandos DOM no navegador integrado. A saída impressa/PDF não foi conferida automaticamente; validar a prévia no navegador de apresentação. Captura da seleção final em `output/demo-frontend.png`.
- Horizontes 30/60/90 verificados no navegador. Com demanda +100% (hipótese extrema editada), o backend calculou 40,53 e a interface destacou Normal → Atenção. O preset de apresentação foi restaurado. Após reforçar o contrato da API, os 34 testes focados de cenários/recomendações/PostGIS também passaram.
- Snapshot de conteúdo de todas as tabelas públicas da aplicação, incluindo cadastros, séries sintéticas/públicas, clima, avaliações e alertas: contagens e SHA-256 antes/depois idênticos. Evidências em `output/demo-before.json`, `output/demo-after.json`; script somente leitura `backend/demo_snapshot.py`. `spatial_ref_sys` é tabela de referência do PostGIS e fica fora do fingerprint.
- Evidência do cenário calculado: `output/demo-api.json`. No banco verificado, referência **20,28**, cenário 90 dias **28,80**, variação **+8,52 pontos**, alternativa com demanda −10% **20,53**. São observações desta execução, não constantes do frontend. A classificação permaneceu Normal: não se força mudança de classe.
- RETE: 91 observações de 01/01 a 31/03/2025; INMET Caxias A237 a 67,17 km, 90 dias completos na mesma janela UTC. O painel informa limitações temporais/espaciais e ausência de avaliação operacional suficiente. Não atribui automaticamente chuva ao poço.

## Arquivos desta implementação

Novos: `frontend/src/DecisionDemo.tsx`, `frontend/src/ScenarioControls.tsx`, `backend/demo_snapshot.py`, este relatório e evidências `output/demo-*`.

Alterados: `frontend/src/Simulator.tsx` (exports e controles compartilhados), `frontend/src/Indicators.tsx` (cartões reutilizáveis com dados da referência), `frontend/src/Pages.tsx` (rota), `frontend/src/App.tsx` (menu), `frontend/src/styles.css` (etapas e impressão), `backend/app/scenarios/schemas.py` (campo aditivo), `backend/app/scenarios/simulator.py` (regras existentes), `backend/tests/test_scenarios.py` (evidência e contrato), `README.md` (acesso).

## Limitações

O índice não é probabilidade e a cobertura não é confiança preditiva. O modelo não projeta nível, drawdown, vazão ou falhas; horas podem saturar em 24 h/dia. Horizontes representam sensibilidade experimental da janela recente. Reduzir demanda na hipótese não comprova solução operacional. Recomendações exigem revisão técnica humana. Não há persistência de decisão nem vínculo operacional novo para RETE. Impressão depende do suporte do navegador; entrega física ou gravação em PDF deve ser escolhida pelo apresentador no diálogo de impressão.

## Roteiro de três minutos

- **0:00–0:30:** abrir a demonstração e mostrar SIM-PI-001, data efetiva, origem sintética, indicadores e cobertura. Explicar índice experimental 0–100.
- **0:30–1:00:** avançar, mostrar preset −30/+20/+10 e horizonte 90 dias; clicar Simular. Ressaltar hipóteses editáveis e cálculo backend.
- **1:00–1:30:** comparar referência/cenário e contribuições. Explicar pressão de demanda e bombeamento saturado; não prometer mudança de classe.
- **1:30–2:00:** abrir Investigações e apontar uma evidência, justificativa e sugestão. O sistema apoia investigação humana, sem diagnosticar equipamento.
- **2:00–2:30:** comparar demanda −10% mantendo demais hipóteses; mostrar diferença e registrar justificativa técnica no resumo. Copiar ou imprimir.
- **2:30–3:00:** abrir RETE e mostrar observações reais, INMET regional e distância. Concluir: “É necessário obter e validar informações adicionais antes de classificar o risco operacional.”
