# Simulador de Cenários — Fase 10

## Objetivo e natureza

Versão `sensitivity-v1.0.0`. Exercício exploratório de sensibilidade do índice multicritério, sem previsão hidrogeológica, meteorológica ou probabilidade de colapso. Os horizontes representam intensidades progressivas de hipóteses aplicadas à janela recente; não criam observações futuras. Os resultados não constituem recomendação operacional automática.

## Linha de base e arquitetura

`app/scenarios/service.py` reutiliza `risk_indicators` de `app/risk/service.py`, que consulta `well_indicators` com a referência solicitada e descarta chuva de setor com origem incompatível. A mesma função alimenta `/wells/{id}/risk`. Sem data, usa a última medição compatível do poço. As consultas limitam as séries a 180 dias até a referência UTC, inclusive; observações posteriores não entram. Os vínculos setoriais são históricos. Classificação e fonte permanecem explícitas, inclusive SIMULATED e UNKNOWN.

`simulator.py` avalia a linha de base e cada cópia temporária com `app/risk/scoring.evaluate`. Normalização, pesos, classificação, cobertura e fatores pertencem exclusivamente ao motor `multicriteria-v1.0.0`. `assumptions.py` modifica indicadores em cópia profunda; `comparison.py` calcula diferenças. As rotas apenas validam o contrato e coordenam o serviço. Não há escrita, nova tabela ou migração.

## Fórmulas e limites

Todos os percentuais devem ser finitos e pertencer a **[-100, +100]**. Esse intervalo demonstrativo permite zerar ou duplicar variáveis não negativas; não é um limite científico de clima ou demanda. Cada parâmetro tem multiplicador `M = 1 + p/100 × g(h)`. `config.py` define `g(30)=1/3`, `g(60)=2/3`, `g(90)=1`. A progressão tem âncora fixa em 90 dias, mesmo se o pedido incluir apenas 30 dias. Os horizontes aceitos são 30, 60 e 90, sem duplicação; a resposta vem ordenada.

| Hipótese | Indicadores alterados | Regra |
|---|---|---|
| Precipitação | `rainfall_30d`, `recent_rainfall_deficit_30d` | `R'=R×Mchuva`; `D'=max(0,1−R'/(30×Aprev))`, sendo Aprev a média diária da janela anterior |
| Demanda | `demand_avg_30d`, `demand_pressure_30d` | `Q'=Q×Mdemanda`; `P'=(1+P)×Mdemanda−1`, preservando a janela anterior |
| Bombeamento | `pumping_hours_avg_30d`, `utilization_avg_30d`, `pumped_volume_avg_30d` | `H'=min(24,max(0,H×Mbomba))`; `U'=max(0,U×Mbomba)`; `V'=V×H'/H` quando H>0 |

A pressão de demanda pode ser negativa (queda relativa), enquanto a demanda absoluta permanece não negativa. Utilização é tempo solicitado e pode exceder 1; o motor satura sua normalização em 100, sem interpretar isso como capacidade hidráulica. Horas são limitadas a 24 h/dia com aviso quando ocorre corte. Volume acompanha a razão das horas efetivas, mantendo vazão. Se horas e volume forem zero, volume permanece zero. Se horas forem zero e volume positivo, volume permanece constante com aviso de inconsistência, pois a razão não é definida.

Mudança zero preserva integralmente cada indicador e reproduz a avaliação de referência. Para chuva, recalcula-se o déficit usando as janelas, nunca o déficit truncado original: isso permite que reduções de precipitação sem déficit inicial passem a gerar déficit somente quando a chuva recente ficar abaixo da anterior.

Não extrapolamos níveis, drawdown, vazão, falhas, tendências ou outras janelas (7/60/90 dias). Elas permanecem contexto histórico de referência. A resposta com indicadores representa uma combinação de contexto histórico fixo e hipóteses sobre a janela recente; não é uma série futura internamente reconstruída. Contagens de dias referem-se à cobertura dos inputs históricos, não a novas observações. A utilização solicitada não é limitada pela hora efetiva: essa diferença permite representar pressão além do dia operacional, explicitamente.

## Score, comparação e insuficiência

O motor aplica `N(x)=min(100,max(0,100×(direção×x−L)/(H−L)))`, média dos critérios por grupo e soma ponderada existente. Exige cobertura mínima de 80% e grupo subterrâneo completo. Dados ausentes permanecem ausentes; não há preenchimento artificial. Alterações não tornam históricos incompletos suficientes. Chuva anterior nula ou incompatível mantém o déficit indisponível.

Diferença absoluta: `Δ=scoreHipotético−scoreReferência`, em pontos. Diferença relativa: `100×Δ/scoreReferência`, apenas com referência diferente de zero. Caso algum score esteja ausente, diferenças são nulas. Cada fator contém subscore antes/depois, diferença e diferença da contribuição ponderada; explicações de aumento, queda, estabilidade ou indisponibilidade seguem os valores realmente calculados. Quando ambos os índices estão disponíveis, a soma das diferenças de contribuição reproduz Δ dentro da precisão numérica.

Não se força mudança diante da saturação. As relações monotônicas são testadas mantendo os demais parâmetros constantes. Cobertura é disponibilidade de dados e não confiança da simulação.

## API e interface

`GET /api/v1/scenarios/config` expõe versão, limites, progressão e presets centralizados. `POST /api/v1/scenarios/simulate` recebe UUID, referência opcional, três percentuais e horizontes. Retorna baseline, indicadores, índices/fatores por horizonte, parâmetros efetivamente aplicados, diferenças, premissas, avisos, proveniência e `nature=HYPOTHETICAL_SENSITIVITY`. Poço inexistente: 404; parâmetros/data/UUID inválidos: 422; ausência de histórico: 200 com status INSUFFICIENT_DATA.

`/simulator` permite buscar/selecionar poço, escolher referência, consultar baseline e ajustar sliders/campos. A seleção da entidade/data limpa o resultado anterior. Sliders não disparam simulação. O botão Simular faz três consultas: cenário selecionado, favorável e estresse severo, usando a mesma referência efetiva. O gráfico Recharts e tabela comparam os três horizontes com a baseline. Trocar hipóteses após executar mostra aviso de resultado anterior. Restaurar parâmetros zera os controles e remove resultados, sem redefinir dados no banco.

Presets demonstrativos, todos editáveis:

| Preset | Chuva | Demanda | Bombeamento |
|---|---:|---:|---:|
| Referência | 0% | 0% | 0% |
| Favorável | +20% | -10% | -15% |
| Estiagem | -30% | +15% | +10% |
| Estresse severo | -60% | +30% | +20% |

## Segurança e calibração futura

Nenhum histórico, cadastro, alerta ou avaliação real é alterado. Resultados só existem em memória/resposta; não usam `risk_assessments`. Testes PostGIS executam em schema temporário com rollback, verificam conteúdo de registros antes/depois e invariância diante de alterações de observações futuras no schema de teste. Não é executado reset do dataset do MVP.

As hipóteses, pesos e limites precisam de revisão por especialistas e calibração com dados reais antes de uso operacional. Próxima fase recomendada: validar parâmetros e relações com especialistas, estabelecer critérios de calibração e incerteza e incorporar dados reais com proveniência. Não acrescentar curvas físicas ou modelos preditivos sem evidência.
