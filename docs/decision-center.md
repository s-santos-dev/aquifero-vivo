# Centro de Decisões Hídricas — entregas A + B

## Objetivo e execução

`/` abre `/decisions`: **onde investigar, por que investigar e o que considerar fazer**. `/dashboard` continua disponível como visão geral. A entrada **Demonstração de Decisão** abre `/demo/decisao`.

Com o banco já preparado: `docker compose up -d db backend frontend`. Abra http://localhost:5173/decisions. Não executar seed/reset. Se o Docker Desktop não detectar alterações dos arquivos montados, execute `docker compose restart frontend`.

## Auditoria e reutilização

O workspace já continha mudanças locais de SIAGAS, RIMAS, INMET, simulador e uma demonstração de seis etapas. Elas foram preservadas; nenhum commit, migration, pipeline, motor de risco ou contrato backend foi alterado nesta entrega. Foram inspecionados README, documentação de indicadores/risco/cenários, rotas, ranking, recomendações e componentes existentes.

Reutilizados: ranking territorial ordenado pelo backend, `MapViewport`/`WellMapMarker`, TanStack Query, helpers HTTP paginados, `MeasurementHistory`, `Indicators`, `Risk`, `ScenarioControls`, Recharts, `RimasHistory` e `ClimateHistory`. A demonstração anterior foi adaptada para cinco etapas.

## Centro de Decisões

- Busca por nome/código; filtros de município, setor, classificação, origem e data; prioridade experimental ou código; lista paginada e mapa. Filtros, seleção e modo ficam na URL e sobrevivem a recarregamento/voltar do navegador.
- Catálogo, setores e ranking são carregados em lote. Filtros locais não consultam risco para todos os poços individualmente. Páginas adicionais do ranking usam a data efetiva da primeira resposta. Apenas o poço selecionado consulta explicação/recomendações. Cache de um minuto para catálogo/ranking no centro.
- Grupos distintos para poços sintéticos e cadastros públicos. Score ausente aparece como avaliação indisponível; não é convertido em zero. Os filtros permitem consultar também registros sem avaliação.
- Modo simples: significado da classificação, três maiores contribuições positivas retornadas pelo motor, cobertura, data, fonte e investigações. Histórico fica sob demanda.
- Modo técnico: indicadores completos, unidades, dias válidos/exigidos, tendências, pesos iniciais/efetivos, subscores, contribuições, metodologia e histórico. Alternar modo não altera cálculos.
- Dicionário com disclosures nativos acessíveis por teclado, incluindo ajuda junto aos indicadores. A cobertura representa disponibilidade, nunca confiança preditiva.
- Histórico: período e indicador editáveis, gráfico/tabela e comparação descritiva com a janela imediatamente anterior. Comparação de médias somente quando ambas têm exatamente um valor válido por dia, a mesma unidade e a mesma origem conhecida. Sem preenchimento de lacunas, previsão ou recálculo de risco.

## Explicações e recomendações

As classificações são as da API: NORMAL, ATTENTION, HIGH, CRITICAL; ausência corresponde a INSUFFICIENT_DATA. Normal não garante ausência de risco real. Score não representa probabilidade.

O resumo utiliza os nomes e as contribuições dos fatores reais. As explicações técnicas vêm de `risk.factors[].explanation`. Grupos indisponíveis são listados e a exigência de cobertura é exibida da resposta.

As recomendações vêm exclusivamente das regras existentes no backend: STATIC_TREND, RAINFALL_DEFICIT, PUMPING_LOAD, DEMAND_PRESSURE, RECENT_FAILURES e DATA_COVERAGE. O frontend acrescenta títulos e nomes legíveis, mantém justificativas/evidências/sugestões e exige avaliação humana. Não cria diagnósticos, recomendações sanitárias, ordens de serviço ou ativação de reservas.

## Demonstração em cinco etapas

1. **Selecionar poço:** SIM-PI-001 somente depois de confirmado no catálogo. Se ausente, mensagem e seleção manual; poços sintéticos sem avaliação suficiente não podem ser simulados.
2. **Entender a referência:** data efetiva, índice/classificação, cobertura, fonte e indicadores em detalhe. Data vazia usa a última medição disponível.
3. **Simular cenário:** preset editável −30% chuva, +20% demanda, +10% bombeamento; restaurar limpa resultados anteriores. Limites vêm de `/scenarios/config`. Hipóteses não são previsões meteorológicas.
4. **Interpretar:** referência e 30/60/90 dias em gráfico ou tabela, diferenças em pontos, fatores da mudança, subscores, avisos, saturação e investigações dos indicadores hipotéticos. Mantém a classificação quando a API não a altera.
5. **Alternativas e resumo:** todos os parâmetros da alternativa são editáveis; presets da configuração são reutilizados. O padrão mantém chuva/bombeamento e muda demanda para +5%. Compara índices, classificações e fatores. Após comparar, gera resumo com fonte, cobertura, hipóteses, resultados, investigações e limitações; copiar usa Clipboard API e imprimir usa `window.print()`.

Avançar/voltar preserva resultados. Editar hipóteses exige nova simulação. Trocar poço/data invalida a análise anterior. Alternar para o exemplo público preserva o estado sintético em memória. Reiniciar limpa a demonstração; não grava dados.

O exemplo público reutiliza RETE/RIMAS e a estação INMET A237 quando importada: cadastro, leituras originais, chuva, distância geodésica, cobertura e interseção das janelas por datas de calendário. O fuso RIMAS não foi confirmado: interseção não significa sincronização temporal ou associação causal. Nenhum score público é calculado a partir dessas séries e dos dados sintéticos.

## Endpoints utilizados

| Endpoint | Uso |
| --- | --- |
| `GET /api/v1/wells`, `/sectors` | Catálogo, origem, filtros e seleção |
| `GET /api/v1/risks/wells` | Ranking, data comum, classes, disponibilidade |
| `GET /api/v1/wells/{id}/recommendations` | Avaliação completa, fatores e regras históricas |
| `GET /api/v1/wells/{id}/indicators` | Indicadores técnicos e cobertura |
| `GET /api/v1/measurements` | Histórico, comparação temporal e RIMAS separado |
| `GET /api/v1/scenarios/config` | Limites e presets existentes |
| `POST /api/v1/scenarios/simulate` | Referência zero, cenário A e B; sem persistência |
| `GET /api/v1/wells/{id}/nearby-climate` | Estações públicas e distância |
| `GET /api/v1/climate/stations/{id}/rainfall` | Chuva diária e cobertura |

O endpoint `/api/v1/alerts` foi auditado e continua na central `/alerts`; o centro usa as recomendações da avaliação selecionada, sem duplicar consultas de alertas.

## Arquivos desta entrega

Novos: `frontend/src/DecisionCenter.tsx`, `frontend/src/DecisionSupport.tsx`, este documento e evidências `output/decisions-*`.

Alterados: `App.tsx` (exports do mapa/menu), `Pages.tsx` (rota inicial), `DecisionDemo.tsx` (fluxo existente), `Indicators.tsx` (todos os indicadores/ajuda), `Risk.tsx` (tipo compartilhado/metodologia), `MeasurementHistory.tsx` (visualização/comparação/data comum), `RimasHistory.tsx` e `ClimateHistory.tsx` (cobertura/interseção), `styles.css` e README. Todos os arquivos de interface ficam em `frontend/src/`.

## Validação e limites

- Backend: **235 testes aprovados**, incluindo PostGIS, com `docker compose exec -T -e RUN_POSTGIS_TESTS=1 backend python -m pytest -q -o cache_dir=/tmp/decisions-pytest-cache`. Dois avisos de depreciação das dependências de teste.
- TypeScript/Vite: `docker compose exec -T frontend npm run build`. Não há framework de testes frontend configurado; nenhuma dependência foi instalada.
- Navegador com API real: ranking, busca, filtros combinados, cadastro público insuficiente, preset, entrada fora dos limites, restauração, simulação, tabela 30/60/90, classificação inalterada, saturação, edição da alternativa, comparação, navegação entre etapas e cópia do resumo.
- Também conferidos: município/setor, ordenação por código, estado vazio, mapa, modo técnico mantendo o índice, comparação histórica completa, insuficiência em 05/02/2024, erro HTTP real provocado por referência inválida e recuperação. Glossário acionado por teclado; centro e controles da demonstração em viewport móvel 390 × 844, e centro em desktop 1440 × 900, sem transbordamento horizontal do documento.
- Nesta base em 10/10/2026: SIM-PI-001, referência 2025-12-30: **20,28 → 28,80**, alternativa +5% demanda **22,76**, todas Normal. São observações desta execução, não valores fixados no frontend.
- Preservação: fingerprints somente leitura de todas as tabelas públicas da aplicação, exceto `spatial_ref_sys`, em `output/decisions-before.json` e `output/decisions-after.json`.
- **13 tabelas com contagens e SHA-256 idênticos**, incluindo 131.400 medições sintéticas, 91 observações RIMAS, 2.160 INMET, 106 poços, 20 setores e 80 vínculos. Evidência consolidada: `output/decisions-validation.json`. Capturas: `output/decisions-center.jpg`, `output/decisions-explanation.jpg`, `output/decisions-demo.jpg`, `output/decisions-mobile.jpg`.
- O mapa usa tiles externos OpenStreetMap. Catálogo/lista e demonstração usam a API local. Paginação em lote é adequada ao catálogo atual, sem promessa de escala ilimitada.
- Simulações só persistem em memória da página. Recarregar a demonstração reinicia o fluxo. A impressão depende do diálogo nativo; a entrega física/PDF é escolhida pelo apresentador.
- Limitação do teste de impressão: o acionamento de **Imprimir relatório** excedeu o tempo de resposta do navegador integrado. O CSS de impressão está implementado, mas a prévia e o PDF final não foram verificados. Nenhum arquivo foi enviado a uma impressora.
- Não há previsão física dos níveis, inferência de recarga ou comprovação de segurança/viabilidade por menor score. Os limites científicos dos motores existentes permanecem válidos.

## Roteiro de três minutos

- **0:00–0:30:** Centro de Decisões; selecionar um poço no ranking e mostrar significado, fonte e uma investigação.
- **0:30–1:00:** abrir demonstração, confirmar SIM-PI-001 e avançar à referência; mostrar data e origem sintética.
- **1:00–1:30:** simular −30/+20/+10; mostrar 30/60/90, diferença e classificação real, sem prometer mudança de classe.
- **1:30–2:00:** interpretar dois fatores, saturação e uma investigação apoiada por evidência.
- **2:00–2:30:** comparar alternativa com demanda +5%; gerar/copiar resumo e apontar limites de uso.
- **2:30–3:00:** mostrar RETE/RIMAS e INMET regional, distância/interseção; explicar que ainda faltam dados operacionais para classificar o poço público.
