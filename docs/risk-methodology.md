# Motor de risco multicritério v1

O motor calcula sob demanda um índice de priorização preventiva de poços, de 0 a 100. Não estima probabilidade de colapso. Versão dos parâmetros: `multicriteria-v1.0.0`.

**O motor de risco v1 utiliza regras multicritério experimentais e dados sintéticos. Seus resultados não constituem previsão validada de esgotamento de aquíferos, nem devem fundamentar decisões operacionais reais sem calibração e validação adequadas.**

## Critérios e normalização

Cada critério usa `N(x) = min(100, max(0, 100 × (direção × x − L) / (H − L)))`. A direção é +1 quando aumento significa maior pressão e −1 para queda de vazão. Nenhum limite foi ajustado à distribuição do dataset sintético ou representa limite hidrogeológico oficial.

| Grupo / peso | Indicador existente | Unidade | Direção | L → H |
|---|---|---|---|---|
| Estresse subterrâneo / 30% | static_level_trend_30d | m/dia | +1 | 0 → 0,10 |
| Estresse subterrâneo | drawdown_trend_30d | m/dia | +1 | 0 → 0,10 |
| Estresse subterrâneo | flow_trend_30d (operations) | (m³/h)/dia | −1 | 0 → 0,10 |
| Déficit de precipitação / 20% | recent_rainfall_deficit_30d | fração | +1 | 0 → 1 |
| Pressão de demanda / 20% | demand_pressure_30d | fração | +1 | 0 → 0,50 |
| Pressão de bombeamento / 20% | pumping_hours_avg_30d | h/dia | +1 | 8 → 24 |
| Pressão de bombeamento | utilization_avg_30d | fração | +1 | 0,50 → 1 |
| Estresse operacional / 10% | failures_30d | dias com falha | +1 | 0 → 10 |

Justificativas demonstrativas: tendências de 0,10 equivalem a uma mudança de aproximadamente 3 unidades em 30 dias; aumento de demanda de 50% corresponde a pressão relativa expressiva; déficit de 100% significa ausência da chuva da janela anterior; 8 horas representa uma jornada e 24 horas o dia completo; utilização 0,50–1 descreve tempo solicitado; dez dias com falha representam um terço da janela. São âncoras ilustrativas, arbitrárias e configuráveis, sem validação científica.

A profundidade absoluta não entra no cálculo: `water_level_m` positivo crescente significa água mais profunda. Chuva compara janelas adjacentes, não normal climatológica. A utilização expressa fração do tempo solicitado, não capacidade hidráulica observada.

Os critérios de cada grupo recebem pesos internos iguais. Não se somam janelas de 30 e 90 dias nem mudanças e tendências da mesma série: a v1 escolhe a janela recente. Demanda usa somente a razão relativa existente, evitando favorecer poços maiores através de variações absolutas em m³/dia. Bombeamento usa média de horas efetivas e utilização solicitada, com orçamento conjunto limitado a 20%; ainda há correlação residual e a utilização representa 10 pontos máximos do total. Volume bombeado foi omitido por correlação com vazão e horas. Falhas usa somente contagem em 30 dias; a recência não entra porque pode estar indisponível mesmo com uma janela completa sem falhas. Os indicadores de 90 dias continuam disponíveis na API de indicadores, mas não são somados ao índice.

## Cobertura, score e explicação

Um grupo está AVAILABLE somente quando **todos os critérios selecionados** estão AVAILABLE e têm valores finitos. É uma política conservadora: não se redistribuem pesos internos em função de dados ausentes. Um grupo incompleto tem subscore nulo; os valores disponíveis permanecem rastreáveis.

Cobertura = soma dos pesos iniciais dos grupos completos. Exige-se cobertura ≥ 0,80 e o grupo subterrâneo completo (incluindo vazão operacional). Caso contrário, score e classificação são nulos e status é INSUFFICIENT_DATA. Ausência nunca vira risco zero. Cobertura mede disponibilidade, não confiança preditiva.

Para avaliação suficiente, peso efetivo = peso inicial / cobertura e contribuição = subscore × peso efetivo. Score = soma das contribuições, limitado a 0–100 para proteger contra erro residual de ponto flutuante. Não arredondamos os valores no contrato; a interface arredonda somente a apresentação. A soma é consistente dentro da precisão de ponto flutuante. Fatores são ordenados por contribuição decrescente, com grupos indisponíveis ao final. Quando o score é indisponível, as contribuições e pesos efetivos são nulos.

Classificação: NORMAL `[0,40)`, ATTENTION `[40,60)`, HIGH `[60,80)`, CRITICAL `[80,100]`. São faixas experimentais de prioridade, sem lacunas para decimais.

## Tempo e proveniência

O serviço reutiliza `well_indicators`, sem nova infraestrutura SQL de medições. `reference_date` é um dia UTC e todas as janelas terminam nessa data. Sem parâmetro, usa a maior data disponível entre medições subterrâneas e operacionais do próprio poço, política já existente nos indicadores. Não retrocede silenciosamente para obter cobertura maior. Sem qualquer medição e sem data solicitada, referência é nula e a análise insuficiente.

As consultas existentes filtram classificação e fonte de acordo com o cadastro. Chuva usa o vínculo setorial vigente na data e o motor descarta o grupo pluviométrico se classificação ou fonte do setor diferirem do poço. Isso evita misturar origens incompatíveis. A resposta identifica classificação e fonte. Para comparar poços, forneça explicitamente a mesma data: a data automática pode variar entre poços.

Reprodutibilidade depende de preservar medições, cadastros, vínculos históricos, código dos indicadores e parâmetros da versão. A v1 não grava snapshots nem avaliações em `risk_assessments`.

## API e frontend

`GET /api/v1/wells/{id}/risk?reference_date=2026-09-20`

Retorna identificação, referência efetiva, origem, versão, natureza experimental, status, score, classificação, cobertura, subscores, fatores e grupos indisponíveis. Cada fator contém inputs com unidade, status, valor original e normalizado, peso inicial e efetivo, contribuição e explicação. Poço inexistente: 404; data inválida: 422; poço sem dados: 200 com análise insuficiente.

Na página de detalhes do poço, Análise de Risco segue o seletor UTC dos Indicadores. A consulta usa TanStack Query e o service HTTP existente; o React apenas apresenta o cálculo da FastAPI. Quando a referência automática dos indicadores chega, ela é enviada explicitamente ao risco. Existem estados de carregamento, erro com nova tentativa e dados insuficientes.

## Configuração e testes

Editar `backend/app/risk/config.py`: `GROUPS` centraliza pesos e critérios (section, key, low, high, direction), `MIN_COVERAGE` controla cobertura e `CLASSIFICATION_LIMITS` controla faixas. Pesos devem ser positivos e somar 1; high deve ser maior que low. Atualize `VERSION` e esta documentação sempre que alterar parâmetros. Schemas refletem as cinco classificações/status suportados.

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_risk.py tests/test_indicators.py tests/test_api_v1.py tests/test_health.py -q
.\.venv\Scripts\alembic.exe check
cd ../frontend
npm run build
cd ..
docker compose config --quiet
docker compose exec -T -e RUN_POSTGIS_TESTS=1 backend python -m pytest tests/test_risk_database.py -q -p no:cacheprovider
```

Testes cobrem normalização, extremos, direção, monotonicidade, soma ponderada, faixas decimais, cobertura, origem incompatível, insuficiência, explicações, consistência de contribuições, contrato FastAPI, encaminhamento da referência e exclusão de observações futuras. Fixtures são pequenas e determinísticas; nenhum reset ou recriação do dataset é necessário. O teste de contrato usa dependência de banco substituída; a validação local da API é adicional.

## Limitações e próxima etapa

Sem calibração científica, previsão, ML, persistência, SIAGAS ou RIMAS. A fase 9 adiciona alertas derivados e recomendações determinísticas. O índice pode não ordenar cenários sintéticos como esperado: tendências recentes e déficits relativos não medem todo o estresse acumulado. Janelas diárias incompletas impedem grupos mesmo quando existem leituras esparsas. Pesos e normalizações exigem validação por especialistas antes de uso real.

Consulta agregada com referência única e consultas em lote implementada na fase 9 para ranking e cores do mapa. Veja [prioritization.md](prioritization.md).

Na comparação determinística de seis poços, dois setores e 180 dias (sem gravação do dataset), os scores médios foram NORMAL 28,1125; DROUGHT 29,7391; SEVERE_STRESS 32,3255. Essa ordem observada não implica separação entre classes ou validação científica. O teste PostGIS usa schema temporário e rollback; não modifica o dataset do MVP.
