# Priorização territorial — Fase 9

## Implementação

O pré-requisito foi confirmado: motor existente em `backend/app/risk/` e 35 testes de risco aprovados antes das alterações. As mudanças locais anteriores foram preservadas. O novo serviço `territorial.py` reutiliza `evaluate` e os cálculos puros de indicadores; não há segundo cálculo de risco.

Consultas em lote: catálogo, dois máximos temporais quando não há data explícita, setores, vínculos históricos e três leituras de medições limitadas a 60 dias. O número de consultas é constante: oito automáticas/seis explícitas. Chuva é calculada uma vez por setor; classificação e fonte dos cadastros/medições devem coincidir. Chuva de setor incompatível com o poço é descartada. Esse recorte cobre todos os inputs da versão `multicriteria-v1.0.0`; mudanças de versão que exijam janelas maiores devem atualizar o serviço e seu teste de equivalência.

Não são lidas as 131.400 medições integralmente. O cálculo ainda ocorre em memória para o catálogo inteiro antes de filtrar/paginar; isso atende o MVP de 80 poços, mas não é estratégia final para grande escala. Não há cache persistente ou snapshots.

## Contratos

`GET /api/v1/risks/wells`: itens estendem RiskResponse com município, ID/código/nome do setor e recomendações. Retorna `total/page/page_size/pages`, `reference_date`, `distribution`, `evaluated`, `insufficient`, `high_priority`. Contagens descrevem o conjunto filtrado, antes da paginação. Filtros: classificação enum NORMAL/ATTENTION/HIGH/CRITICAL/INSUFFICIENT_DATA, UUID do setor, município exato sem diferenciar maiúsculas, referência ISO, paginação 1–100 itens. Ordenação estável por classe, score, código e UUID.

`GET /api/v1/alerts`: mesmos filtros e paginação; cada item traz `id`, `kind`, `message`, `evaluation` completa, incluindo sugestões. HIGH/CRITICAL acionam INVESTIGATION e insuficiência aciona DATA_QUALITY. Identidade é poço:data:versão:tipo. ATTENTION/NORMAL não acionam alertas. Resultados são derivados, sem escrita no model Alert existente. Não há reconhecimento/fechamento operacional nesta versão.

`GET /api/v1/wells/{id}/recommendations`: retorna `risk`, `rules_version`, `recommendations`; 404 para poço inexistente, 422 para data/UUID inválidos. Poço sem medições retorna insuficiência e regra de verificação de dados. Cada recomendação identifica regra, justificativa, sugestões e evidências com unidade/status/normalização. Limites e regras constam no README.

O contrato `/wells/{id}/risk` foi preservado. As coleções escolhem a última data global de medições compatíveis de poços; as rotas individuais mantêm data automática por poço. Fornecer `reference_date` garante equivalência temporal entre coleções e detalhes. Nenhuma observação posterior à referência é lida; vínculos são escolhidos na data.

## Interface e transparência

Visão geral inclui distribuição, cobertura e ranking paginado com filtros. Alertas é uma rota navegável real. Mapa existente usa avaliações do backend para cores, filtros de classe/setor e popups com índice, referência, cobertura, fator e detalhes. Dados insuficientes são cinza; API indisponível exibe erro, sem simular avaliação.

Os links de ranking, alertas e mapa levam a referência efetiva em query string. Indicadores, risco e recomendações dos detalhes seguem esse seletor. O painel mostra fatores, grupos indisponíveis, origem, versão e aviso experimental. As recomendações dependem de inputs finitos AVAILABLE; grupos incompletos não invalidam outras evidências válidas, mas a insuficiência global permanece visível.

Não há previsão validada de falha, probabilidade de colapso, confiança preditiva, operação automática, custos financeiros, ML ou integração externa. A carga local pode conter apenas NORMAL; não são fabricados alertas para preencher a interface. Datas iniciais do histórico demonstram insuficiência e suas sugestões.

## Arquivos

Criados: `app/risk/territorial.py`, `app/risk/recommendations.py`, `app/schemas/priority.py`, `tests/test_priorities.py`, `tests/test_priorities_database.py`, `frontend/src/Priorities.tsx`, esta documentação. Modificados: rotas v1, App/mapa/navegação, Pages/dashboard, Indicators/data, Risk/recomendações, CSS, README e documentos de arquitetura/modelo/risco/validação. O motor, schema, testes e componente de risco da fase anterior também foram incluídos no versionamento.

Validação e limitações efetivamente observadas constam em [validation.md](validation.md).
