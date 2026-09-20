# Dataset operacional sintético

O gerador em `backend/app/simulation/generator.py` produz dados para desenvolvimento e testes. Ele não ingere nem imita registros de uma fonte identificável. Todos os registros têm `data_classification=SIMULATED`, `is_synthetic=true`, cenário, seed e versão do gerador.

## Saídas

Uma execução padrão produz:

| Arquivo | Granularidade | Linhas |
| --- | --- | ---: |
| `sectors.csv` | cadastro do setor | 20 |
| `wells.csv` | cadastro do poço | 80 |
| `sector_daily.csv` | setor × dia | 14.600 |
| `well_daily.csv` | poço × dia | 146.000 |
| `manifest.json` | execução | 1 |

O manifesto contém configuração, aviso de uso, contagens e SHA-256 dos CSVs. A CLI recusa destinos fora de `data/simulated` para reduzir o risco de mistura com `data/raw` e `data/processed`.

## Relações modeladas

- A precipitação combina sazonalidade, ocorrência de evento e intensidade. `DROUGHT` e `SEVERE_STRESS` reduzem a mesma realização meteorológica base usada em `NORMAL`.
- A recarga é um estado com memória: 95,5% do índice anterior permanece a cada dia e a chuva recente atualiza o restante. Por isso uma sequência seca tem efeito persistente.
- A demanda deriva da população, consumo per capita, sazonalidade térmica, dia da semana, crescimento populacional e cenário.
- A demanda é distribuída entre os poços do setor proporcionalmente à capacidade. Horas solicitadas e utilização resultam dessa alocação.
- O estresse do poço acumula déficit de recarga e utilização acima de 62%, com dissipação lenta. Ele reduz gradualmente a vazão disponível e aprofunda o nível estático.
- O nível dinâmico é o nível estático mais o rebaixamento produzido por vazão e utilização. Nesta convenção, os níveis são profundidades abaixo da superfície; valores maiores são piores.
- O risco combina déficit de recarga, utilização, estresse acumulado, rebaixamento persistente e falha ativa. Falhas também se tornam mais prováveis sob utilização e estresse altos.

Os parâmetros são simplificações operacionais plausíveis, não uma calibração hidrogeológica de um aquífero real. O dataset não deve ser usado para decisões de operação, políticas públicas ou comunicação factual.

## Cenários

| Cenário | Chuva | Demanda | Recarga | Acúmulo de estresse | Falhas |
| --- | ---: | ---: | ---: | ---: | ---: |
| `NORMAL` | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| `DROUGHT` | 0,52 | 1,12 | 0,82 | 1,28 | 1,55 |
| `SEVERE_STRESS` | 0,24 | 1,28 | 0,62 | 1,72 | 2,30 |

Os valores são multiplicadores relativos, mantidos em `SCENARIO_PARAMETERS`. Uma seed local de NumPy torna a execução reproduzível; o gerador não usa estado aleatório global.

## Proteção de proveniência

A persistência e os schemas internos reconhecem `REAL`, `PUBLIC` e `SIMULATED`. A API normal expõe a classificação e `is_synthetic` derivado dela. Não há contratos paralelos para mocks. Nos cadastros legados, a migration 0004 preserva origem desconhecida como `UNKNOWN`.

A migration 0003 mantém a proteção existente contra classificação automática de medições legadas. A 0004 é aditiva e não apaga registros.

## Campos persistidos e expostos

| Campo | Unidade | Origem no seed | Descrição |
| --- | --- | --- | --- |
| `code` | texto | SIMULATED | Código artificial `SIM-PI-001` / `SIM-SEC-001` |
| `location.coordinates` | graus, longitude/latitude | SIMULATED | Ponto fictício SRID 4326 |
| `boundary` | GeoJSON MultiPolygon | SIMULATED | Faixa geográfica de demonstração |
| `depth_m` | m | SIMULATED | Profundidade total do poço |
| `water_level_m` | m abaixo da superfície | SIMULATED | Nível estático; `static_level_m` no CSV |
| `dynamic_level_m` | m abaixo da superfície | SIMULATED | Nível sob bombeamento |
| `flow_rate_m3_h` | m³/h | SIMULATED | Vazão diária simulada |
| `precipitation_mm` | mm/24h | SIMULATED | Chuva por setor, não por estação real |
| `daily_demand_m3` | m³/dia | SIMULATED | Demanda alocada a cada poço |
| `pumped_volume_m3` | m³/dia | SIMULATED | Vazão × horas efetivas |
| `runtime_hours` | h/dia | SIMULATED | Entre 0 e 24 |
| `utilization` | razão adimensional | SIMULATED | Horas solicitadas/24; pode superar 1 quando há demanda não atendida |
| `operational_failure` | booleano | SIMULATED | Ocorrência de falha simulada |
| `operating_status` | texto | SIMULATED | OPERATING, IDLE ou FAILED |
| `source` | texto | SIMULATED | `SIMULATED:AQUIFERO_VIVO` identifica propriedade do seed |
| `data_classification` | enum | SIMULATED | Proveniência em todas as entidades gravadas |
| `is_synthetic` | booleano | SIMULATED | Derivado na API; explícito nos CSVs |

`risk_score` e `risk_level` já existentes no gerador são indicadores de **pressão demonstrativa**, somente no dataset. Não são gravados em `RiskAssessment` ou `Alert`, nem constituem motor de risco. São usados para comparar cenários nos testes.

## Coeficientes e reprodução

Os multiplicadores dos cenários estão em `scenarios.py`. `relationships.py` centraliza os demais coeficientes em `ModelParameters`: população (25–90 mil por setor), consumo (0,145–0,205 m³/pessoa/dia), vazão nominal (28–82 m³/h), eficiência (0,88–0,98), nível estático inicial (10–31 m), profundidade adicional (42–105 m), coeficientes de falha, demanda e rebaixamento. Os demais valores exatos e seus nomes estão nessa dataclass.

A recarga retém 0,955 do estado anterior, limitada a 0,03–1,20. O estoque de pressão retém 0,986, soma 0,052 × déficit e 0,040 × excesso de utilização, multiplicados pelo cenário. Com chuva e redução de pressão, os estados recuperam gradualmente; não há previsão ou calibração física. Aleatoriedade local NumPy com consumo fixo de sorteios mantém a comparação dos cenários. Versão atual: 2.0.0; seed padrão: 42. Reprodutibilidade numérica pressupõe a mesma versão das dependências NumPy.

Validação exige séries completas sem duplicação, limites geográficos, relações válidas, valores finitos/não negativos, níveis ordenados abaixo da profundidade, horas 0–24 e compatibilidade volume/vazão/horas (tolerância de 0,1 m³ por arredondamento). O seed valida novamente antes da escrita e normaliza pelos schemas Pydantic comuns.
