# Indicadores do MVP

Os indicadores são calculados sob demanda a partir das tabelas normais de medições. Não são gravados em `risk_assessments`, não atribuem risco e não representam previsão. A API devolve `value`, `status`, `unit`, `observed_days` e `required_days` para cada indicador. `INSUFFICIENT_DATA` sempre corresponde a `value: null`; zero é um valor observado.

## Tempo, proveniência e disponibilidade

- `reference_date` é uma data civil em UTC. A janela de N dias inclui essa data e os N−1 dias anteriores. A data de referência é também o limite máximo das consultas SQL. Sem parâmetro, o poço usa a data mais recente entre suas medições subterrâneas e operacionais; o setor usa a última data de chuva disponível.
- Poços usam a classificação e a fonte do próprio cadastro para selecionar suas medições. A chuva usa a medição diária já associada ao setor vinculado ao poço no fim da data de referência, com a classificação e a fonte desse setor. A chuva do setor não é média, mediana ou soma espacial entre poços: no simulador existe uma única série de precipitação por setor e dia. Setores agregam somente poços com a mesma classificação e fonte do setor. Isso impede combinar séries de origens diferentes por acidente.
- Uma janela está disponível somente se cada dia civil possuir exatamente uma medição com o campo necessário. Dia ausente, valor nulo ou várias medições no mesmo dia tornam a janela insuficiente. Não há interpolação nem conversão de ausência em zero. Essa regra corresponde ao dataset diário do MVP; fontes com várias leituras diárias precisarão de uma política explícita de consolidação.
- Indicadores `current_*` exigem uma medição na própria data de referência. Séries com data anterior não são apresentadas como atuais. `days_since_last_failure` fica indisponível quando nenhuma falha foi observada na janela consultada.
- Os cálculos consultam no máximo 180 dias por tipo de medição para um poço. Os índices `(well_id, measured_at)` e `(service_sector_id, measured_at)` já existiam. O setor lê uma única vez as operações de todos os poços elegíveis; não faz uma consulta por poço.

## Fórmulas

Nas fórmulas abaixo, `média_N` é a média dos N valores diários da janela finalizada em `reference_date`. `média_anterior_N` corresponde aos N dias imediatamente anteriores a essa janela. `tendência_N` é a inclinação da regressão linear ordinária de todos os N pontos diários, em unidade por dia. `mudança_N = média_N − média_anterior_N`, em unidade original; precisa de 2N dias. Sinal positivo significa aumento numérico da variável.

| Indicador | Fórmula e significado | Unidade | Janela e entrada |
| --- | --- | --- | --- |
| `rainfall_7d`, `_30d`, `_60d`, `_90d` | Soma da precipitação diária | mm | 7/30/60/90; `RainfallMeasurement.precipitation_mm` do setor |
| `rainfall_avg_previous_30d`, `_90d` | Média diária da janela anterior, sem sobreposição | mm/dia | 30 ou 90 dias anteriores; chuva do setor |
| `recent_rainfall_deficit_30d` | `max(0, 1 − chuva_30d / chuva_anterior_30d)`; déficit recente relativo | fração | 60 dias; indisponível se referência anterior for zero; não representa seca climatológica |
| `current_static_level`, `current_dynamic_level` | Leitura da data de referência | m de profundidade | Dia atual; `water_level_m` e `dynamic_level_m` |
| `static_level_change_30d`, `_60d`, `_90d`; `dynamic_level_change_*` | Diferença entre médias de duas janelas adjacentes | m | 2N dias; níveis respectivos |
| `static_level_trend_30d`, `_60d`, `_90d`; `dynamic_level_trend_*` | Inclinação da regressão de todos os pontos | m/dia | N dias; níveis respectivos |
| `current_drawdown` | Nível dinâmico menos nível estático | m | Dia atual; ambos os níveis |
| `drawdown_avg_30d`, `_60d`, `_90d` | Média diária da diferença dinâmico − estático | m | N dias; ambos os níveis |
| `drawdown_trend_30d`, `_90d` | Inclinação da diferença diária | m/dia | N dias; ambos os níveis |
| `current_flow_rate`; `flow_avg_7d`, `_30d`, `_90d` | Leitura atual ou média da vazão | m³/h | Dia atual ou N dias; `flow_rate_m3_h` |
| `flow_change_30d`, `_90d`; `flow_trend_30d`, `_90d` | Diferença entre médias adjacentes; inclinação diária | m³/h; m³/h/dia | 2N ou N dias; vazão |
| `pumping_hours_avg_7d`, `_30d`, `_90d` | Média das horas diárias de bombeamento | h/dia | N dias; `runtime_hours` |
| `pumped_volume_avg_7d`, `_30d`, `_90d`; `pumped_volume_change_30d`, `_90d`; `pumped_volume_trend_30d`, `_90d` | Média, diferença de médias e inclinação do volume diário | m³/dia; m³/dia² na tendência | N ou 2N dias; `pumped_volume_m3` |
| `demand_avg_7d`, `_30d`, `_90d`; `demand_change_30d`, `_90d`; `demand_trend_30d`, `_90d` | Média, diferença de médias e inclinação da demanda diária | m³/dia; m³/dia² na tendência | N ou 2N dias; `daily_demand_m3` |
| `demand_pressure_30d` | `média_recente_30d / média_anterior_30d − 1`; positivo indica aumento relativo | fração | 60 dias de demanda; referência zero retorna dados insuficientes |
| `current_utilization`; `utilization_avg_7d`, `_30d`, `_90d` | Carga planejada sobre a capacidade nominal diária simulada; média da fração | fração | Dia atual ou N dias; `utilization` |
| `failures_30d`, `_90d` | Soma dos registros diários `operational_failure=true` | falhas | N dias; exige `true` ou `false` em todos os dias |
| `days_since_last_failure` | Dias desde a última falha observada | dias | Até 180 dias consultados; nulo se não houve falha observada |
| `well_count` | Contagem de poços vinculados ao setor na data | poços | Vínculo `WellSector` vigente |
| `total_demand_avg_7d`, `_30d`, `_90d`; `total_pumped_volume_avg_*` | Soma diária entre todos os poços elegíveis, seguida de média temporal | m³/dia | N dias; só disponível se todos os poços tiverem exatamente um valor no dia |
| `total_demand_trend_30d`, `total_pumped_volume_trend_30d` | Inclinação da soma diária do setor | m³/dia² | 30 dias; exige todos os poços em cada dia |

Para todos os indicadores, uma janela incompleta devolve `INSUFFICIENT_DATA`, com o número de dias válidos e exigidos. Não são calculadas médias simples de níveis subterrâneos entre poços. A demanda e o volume são somados por dia antes da média temporal, pois são grandezas aditivas.

## Convenção e limites

### Níveis subterrâneos e drawdown

No simulador, `water_level_m` recebe `static_level_m`, definido como profundidade em metros **abaixo da referência**. O código parte de uma profundidade estática basal e soma `static_stress_weight × stress_stock`; portanto, valor numérico maior significa água mais profunda e, consequentemente, **rebaixamento**. `dynamic_level_m` recebe `dynamic_level_m`, na mesma referência e unidade. O simulador o calcula como `static_level + pumping_drawdown`, limita ambos à profundidade do poço menos a folga de fundo e grava `drawdown_m = max(0, dynamic_level − static_level)`. Por isso, `dynamic_level_m − water_level_m` é exatamente o drawdown demonstrativo usado pela camada de indicadores. A restrição do banco exige nível dinâmico maior ou igual ao estático. A interpretação só deve ser aplicada a fontes reais após conferir seus marcos de medição e unidades.

### Déficit recente de chuva e utilização

`recent_rainfall_deficit_30d` compara duas janelas adjacentes do próprio histórico disponível. É uma medida relativa do MVP, não uma normal climatológica e não deve ser interpretada como seca climatológica. Uma referência de chuva igual a zero não permite calcular a razão e retorna dados insuficientes; excesso de chuva retorna déficit zero.

O simulador define a capacidade nominal diária de cada poço como `nominal_flow_m3_h × efficiency × 24`. A demanda setorial é repartida proporcionalmente à capacidade horária eficiente de cada poço. Assim, `utilization = requested_volume / (nominal_flow_m3_h × efficiency × 24)`, equivalente a `requested_runtime / 24`. É uma carga planejada em relação à capacidade nominal simulada, calculada antes da redução de vazão por estresse, de falhas e do volume efetivamente bombeado. Ela é coerente para descrever pressão de demanda no cenário sintético, mas não deve receber peso elevado no motor de risco até existir uma capacidade observada ou uma política de capacidade validada para dados reais. As medições atuais são sintéticas e as relações do simulador não foram validadas cientificamente. Nenhum indicador deve ser utilizado para decisões operacionais reais.
