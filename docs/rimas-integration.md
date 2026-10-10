# Fase 12 — histórico real RIMAS/SGB

Validação local em **10/10/2026**. Integração operacional de um piloto real, além de fixtures: **RETE, Teresina/PI, `idt_ponto=2200034952`**, de **01/01/2025 a 31/03/2025**. Foram obtidas e importadas **91 observações**, sem rejeições ou duplicatas de identidade, em 90 dias. Em 28/01 há duas leituras: **07:00, 18,77 m, sequência 3371** e **13:00, 18,79 m, sequência 3372**. Ambas permanecem disponíveis.

## Serviços e cobertura verificados

| Serviço oficial | Evidência / resultado | Uso no piloto |
| --- | --- | --- |
| [Portal RIMAS](https://rimasweb.sgb.gov.br/layout/) | Consulta e exportação oficiais; página inicial informava 508 poços e 269 municípios | Descoberta do exportador CSV |
| [FeatureServer RIMAS: camadas](https://geoportal.sgb.gov.br/server/rest/services/hidrologia/rimas/FeatureServer/layers?f=pjson) | 0: Rimas; 1: amostras; 2: aquíferos; 3: Nível D´Água; 4: Nível D´Água Bruto; 5: construção; 6: química | Inspeção do contrato, sem ingestão de séries ArcGIS |
| [MapServer/3](https://geoportal.sgb.gov.br/server/rest/services/hidrologia/rimas/MapServer/3?f=pjson) e [MapServer/4](https://geoportal.sgb.gov.br/server/rest/services/hidrologia/rimas/MapServer/4?f=pjson) | Metadados acessíveis; tabelas de nível e nível bruto | Consultas de dados deram timeout; não significa ausência de séries |
| [Hosted SIAGAS: camadas](https://geoportal.sgb.gov.br/server/rest/services/Hosted/siagas_web/FeatureServer/layers?f=pjson) | 0: legado; 1: poços; **2: Poços Rimas** | Cadastro nacional da estação |
| [Hosted/2/query](https://geoportal.sgb.gov.br/server/rest/services/Hosted/siagas_web/FeatureServer/2/query?f=json&where=str_uf%3D%27PI%27&outFields=idt_ponto%2Cstr_uf%2Cstr_municipio%2Cstr_nome_ponto%2Cnum_profundidade%2Cstatus_rimas&outSR=4326&resultRecordCount=100) | **28 cadastros PI**, resposta sem `exceededTransferLimit` | Verificação regional, identidade e geometria |
| [Detalhe RETE](https://rimasweb.sgb.gov.br/layout/detalhe.php?ponto=2200034952) | Estação local, nível indicado em metros, interface com exportação | Evidência da unidade e descoberta da requisição |
| [Exportador CSV](https://rimasweb.sgb.gov.br/layout/exportaDadosGrafico.php) | POST oficial, resposta `application/csv`, arquivo original preservado | **Fonte efetiva das 91 observações** |

A extensão declarada da camada 0 do serviço `hidrologia/rimas` está entre longitudes aproximadamente −46,27/−44,53 e latitudes −15,30/−10,51, na Bahia. **Não foi tratada como cobertura nacional ou evidência de inexistência de poços no Piauí.** A camada nacional Hosted/2 foi consultada separadamente. Tabelas ArcGIS 3/4 anunciam paginação, limite 1000, `objectid` e campos de data em UTC; consultas de séries excederam os timeouts de 25–30 s. O fuso dos campos ArcGIS não foi transferido para o CSV do portal.

Resultado de elegibilidade: **uma estação com série acessível e verificada para este piloto**; **27 outros cadastros PI com elegibilidade temporal ainda não verificada**. Os 28 cadastros não são 28 séries confirmadas. Não foi feito inventário temporal completo da rede. O período efetivamente baixado/validado é janeiro–março de 2025; não se declara disponibilidade de todo o histórico de cada estação.

O retorno nacional preservado em `data/raw/rimas/research/hosted-pi.json` inclui Alvorada do Gurguéia, Cristino Castro, Jaicós, Teresina, São Miguel do Tapuio, Domingos Mourão, Francisco Santos, Itainópolis, Cocal dos Alves, Buriti dos Lopes, Brasileira, Castelo do Piauí, Wall Ferraz, Lagoa do Sítio, Jatobá do Piauí, Ipiranga do Piauí, Pedro Laurentino, Oeiras, Conceição do Canindé, Picos, Alto Longá, José de Freitas, Altos, Pau D’Arco do Piauí, União, Monsenhor Gil, Beneditinos e Demerval Lobão. Isso descreve cadastros consultados, não disponibilidade de séries.

## Aquisição e limites

O exportador recebe `acao=exportacao`, `tipoExp=expCsv`, `grafico=nivelDagua`, `idponto`, `intervaloDataMin` e `intervaloDataMax` em `DD/MM/AAAA`. É uma operação de leitura. Não são extraídas observações de gráficos ou HTML. O CSV não possui paginação: o período é limitado a **366 dias inclusivos**, o arquivo a **2 MB**, e a transformação a **10.000 registros**. Timeout 30 s, até duas repetições, espera limitada; HTTP 403 e erros de contrato interrompem a coleta. Nenhuma autenticação ou restrição é contornada. A consulta cadastral exata solicita até duas feições e rejeita truncamento ou ambiguidade.

`extract.py` cria um diretório exclusivo por lote, sem sobrescrever arquivos. `observations.csv` mantém os bytes originais; `manifest.json` preserva URLs, seleção, requisição, cabeçalhos, data UTC da extração, cadastro oficial e SHA-256. Reprocessar verifica o checksum. Essa imutabilidade é do fluxo da aplicação; não é armazenamento WORM. Arquivos brutos e relatórios processados ficam fora do Git. A fixture versionada é um subconjunto de cinco linhas oficiais, sem alteração de valores/horários, com origem documentada no manifesto.

Lote operacional: `20261010T165320Z-a225b869`, extraído às `2026-10-10T16:53:20.312086+00:00`. SHA-256 do CSV: `cf608e3c186b2b027a67f18932e8b3f582353aea9387b10bbe32878cdc8a4126`.

## Identidade, campos e persistência

Cadastro SIAGAS descreve o poço; RIMAS descreve observações ao longo do tempo. A identidade compartilhada é **`idt_ponto`**, confirmado no cadastro nacional, no detalhe oficial e na primeira linha do CSV. Não há associação por proximidade ou nome.

| Campo original / evidência | Destino | Regra |
| --- | --- | --- |
| `Id Ponto` / `idt_ponto` | `station_code`, `Well.source_record_id` | Correspondência textual exata |
| Número de sequência | `source_record_id` | Identidade original, obrigatória |
| Data da medição + Hora da medição | `measured_at`, `original_date`, `original_time` | Relógio original sem timezone inventado |
| Nível da água | `observed_level_m`, `original_value` | Decimal com vírgula; metros verificados na página oficial |
| Bombeando | `pumping`, `original_pumping` | `S`, `N` ou desconhecido |
| Vazão | `source_metadata.original_flow` | Somente original; definição/unidade não verificadas, sem conversão operacional |
| Consulta em | `portal_query_time` | Horário de geração do portal, fuso não declarado |
| Extração / lote / URL / checksum | `source_metadata` | Proveniência da aquisição |
| Qualidade, marco e fuso ausentes | Metadados explícitos | `NOT_PROVIDED`, `UNKNOWN`, `UNKNOWN` |

Migration **0006**, após 0005: cria somente `groundwater_observations`. Ela é necessária porque `groundwater_measurements.water_level_m` representa o nível usado pelo fluxo diário existente, enquanto o portal não confirma referência nem condições de nível estático. A nova tabela usa timestamp **sem timezone**, valor decimal, unidade, dataset, estação, sequência, bombeamento e JSONB. Tem FK do poço, índice `(well_id, measured_at)` e unicidade `(source, dataset, station_code, source_record_id)`. Restringe origem a RIMAS/PUBLIC e unidade a metros. Não transforma ausência em zero nem inventa nível dinâmico, chuva ou demanda.

UUIDs estáveis: `uuid5(NAMESPACE_URL, 'SIAGAS:'+idt_ponto)` para o cadastro, e `uuid5(NAMESPACE_URL, 'RIMAS:PORTAL_NIVEL_DAGUA:'+idt_ponto+':'+sequencia)` para a observação. A estação RETE não estava entre os 25 cadastros anteriores: foi criado **um** cadastro público SIAGAS, com origem cadastral Hosted/2 e operação desconhecida. UUID local: `1b2e8ad0-1c88-5d1d-a102-2603a45a2026`.

O loader valida o lote inteiro e conflitos antes de inserir, dentro de transação e sob o mesmo advisory lock da carga SIAGAS. Cadastro já existente é consultado e **não atualizado**. Vínculos ambíguos e identidades protegidas abortam. Repetição idêntica não modifica nem timestamps de auditoria nem a proveniência da primeira aquisição. Revisão conflitante de sequência existente é recusada para análise explícita; não se escolhe silenciosamente uma versão. Duplicatas idênticas dentro de um arquivo são contabilizadas; conteúdos divergentes para a mesma sequência são todos rejeitados. Sequências distintas no mesmo dia permanecem distintas.

## Tempo, qualidade e indicadores

A série do piloto tem leituras diárias em horários variados, um dia com duas leituras, nenhuma lacuna de dia no intervalo solicitado e nenhuma indicação `S`. Os intervalos entre leituras variam de **3 a 47 horas**; presença de uma leitura por data civil não implica amostragem regular de 24 horas. Isso **não certifica nível estático**, instrumento, referência vertical ou qualidade científica. O portal não traz marcadores de qualidade por linha. Valores não finitos, vazios, inválidos, fora da precisão/capacidade decimal, horários inválidos e registros fora do período são rejeitados. Níveis negativos finitos permanecem como observações com referência desconhecida: uma convenção de sinal não é inferida.

A [apresentação oficial RIMAS](https://rimasweb.sgb.gov.br/layout/includes/apresentacao.php) descreve consistência e tratamento antes da disponibilização. Ainda assim, o CSV não identifica por linha o estágio de tratamento nem estabelece equivalência à tabela ArcGIS 3 ou 4. O dataset é **`PORTAL_NIVEL_DAGUA`**, `treatment=PORTAL_EXPORT_UNSPECIFIED`; “bruto” nos diretórios significa arquivo original da aquisição, sem afirmar que seja a tabela “Nível D´Água Bruto”.

Não há média diária, seleção da última leitura, interpolação ou preenchimento. `eligible_for_indicators=false`. Indicadores, motor multicritério, simulador e relógio de referência continuam lendo as tabelas anteriores; nenhuma observação desta nova tabela entra nesses cálculos. RETE retorna **`INSUFFICIENT_DATA`, score e classificação nulos**, inclusive na referência 31/03/2025. Nenhuma chuva, demanda ou setor sintético foi associado.

Política diária investigada, mas **não implementada**: uma camada derivada separada precisaria de fuso e referência confirmados, critérios de qualidade/instrumento e exclusão ou tratamento fundamentado do bombeamento. Um candidato a avaliar seria uma medida representativa por dia (por exemplo mediana de leituras comparáveis), preservando IDs contribuintes, quantidade, amplitude e versão da regra; isso não pode ser adotado sem avaliação hidrogeológica. Lacunas continuariam ausentes. A regra atual de exatamente uma medição diária válida permanece intacta; o dia com duas observações do piloto não foi reduzido a uma leitura.

## Comandos reproduzíveis

```powershell
docker compose up -d

# Somente aquisição e validação; período configurável
docker compose exec -T backend python -m app.ingestion.rimas.cli --station 2200034952 --from 2025-01-01 --to 2025-03-31

# Aquisição oficial + carga transacional
docker compose exec -T backend python -m app.ingestion.rimas.cli --station 2200034952 --from 2025-01-01 --to 2025-03-31 --load

# Reprocessamento offline do lote efetivamente importado
docker compose exec -T backend python -m app.ingestion.rimas.cli --batch /data/raw/rimas/20261010T165320Z-a225b869 --load

# Alternativa: CSV obtido manualmente do exportador; identidade cadastral verificada online
docker compose exec -T backend python -m app.ingestion.rimas.cli --station 2200034952 --from 2025-01-01 --to 2025-03-31 --file /data/raw/rimas/research/teresina-2025.csv
```

O padrão é somente validar. `--load` exige ausência de rejeições; rejeições geram relatório e código de saída 2, sem escrita. Cada execução gera relatório próprio em `data/processed/rimas/` com aceitos, rejeitados, duplicatas, dias sem leitura e dias com múltiplas leituras. Reprocessamento do lote: **0 cadastros / 0 observações criados, 91 observações inalteradas**.

## API e frontend

Rotas existentes, com paginação máxima de 100 itens:

```text
GET /api/v1/wells?source=RIMAS
GET /api/v1/wells/1b2e8ad0-1c88-5d1d-a102-2603a45a2026
GET /api/v1/measurements?type=groundwater&source=RIMAS&well_id=1b2e8ad0-1c88-5d1d-a102-2603a45a2026&measured_from=2025-01-01T00:00:00&measured_to=2025-03-31T23:59:59&page_size=100
GET /api/v1/wells/1b2e8ad0-1c88-5d1d-a102-2603a45a2026/risk?reference_date=2025-03-31
```

`source=RIMAS` em poços seleciona existência de observações; a fonte cadastral continua SIAGAS. Campo aditivo `has_rimas_observations`. Em medições, `type=groundwater` inclui observações RIMAS; `water_level_m` permanece **null** nelas, com valor em **`observed_level_m`**. Novos campos opcionais: unidade, dataset, sequência, bombeamento e metadados. Séries anteriores mantêm seus valores/timestamps e recebem null nos campos novos. A consulta unificada sem filtro pode incluir origens diferentes; o frontend solicita RIMAS explicitamente para o gráfico real.

`measured_at` RIMAS retorna ISO **sem Z/offset**. Filtros temporais RIMAS usam componentes do relógio original; mesmo que o cliente inclua um offset, ele não estabelece o fuso da fonte. A representação UTC intermediária no UNION serve apenas à ordenação SQL e é substituída pelo timestamp original no payload. Comparações cronológicas globais entre fusos conhecidos e desconhecidos não constituem alinhamento científico de séries.

Na lista e no mapa existe filtro de estações com série RIMAS; marcadores públicos permanecem distintos dos sintéticos. Nos detalhes de RETE, gráfico de pontos, datas inicial/final (até 366 dias), tabela com 20 leituras por página, bombeamento, origem, qualidade ausente, extração e insuficiência dos indicadores. O navegador carrega no máximo dez páginas da API (1000 observações) e indica truncamento; intervalos menores permitem consultar o restante. Não há linha ligando lacunas nem mistura de fontes. Dashboard apresenta observações RIMAS separadas das 131.400 medições de simulação.

## Validação real e preservação

**192 testes backend aprovados**, incluindo PostGIS, fixtures oficiais offline, falhas HTTP, contrato CSV, limite de período/tamanho, identidade exata/ambígua, múltiplas leituras, duplicatas conflitantes, valores inválidos, bombeamento, proveniência, paginação, filtros, idempotência e recusa do risco. Dois avisos de depreciação já existentes de Starlette/httpx/anyio. TypeScript/Vite aprovado; `alembic check`: sem operações pendentes; `docker compose config --quiet`: aprovado.

Antes da primeira carga foram calculados SHA-256 de **todo o conteúdo das seis tabelas anteriores, incluindo IDs, auditoria, metadados e geometrias**, com linhas em ordem por ID. Depois, os mesmos hashes e contagens foram confirmados. O escopo `wells` exclui apenas o código do novo cadastro, que não existia antes. Evidências: [antes](../output/rimas-before.json), [depois](../output/rimas-after.json), [relatório operacional](../output/rimas-validation.json).

| Conteúdo preservado | Quantidade |
| --- | ---: |
| Poços anteriores (80 sintéticos + 25 SIAGAS) | 105 |
| Setores | 20 |
| Vínculos poço–setor | 80 |
| Medições subterrâneas sintéticas | 58.400 |
| Medições operacionais sintéticas | 58.400 |
| Medições pluviométricas sintéticas | 14.600 |
| **Total sintético intacto** | **131.400** |

Estado final: **106 poços** (80 sintéticos + 26 SIAGAS, um com monitoramento RIMAS), 20 setores, 80 vínculos, 131.400 medições sintéticas e **91 observações públicas RIMAS**. Nenhum dado anterior foi excluído ou sobrescrito.

O navegador real exibiu 91 pontos e a tabela, com origem e fuso desconhecido, e permitiu consultar as duas leituras de 28/01. [Captura do histórico](../output/rimas-frontend.png). O piloto foi baixado da fonte oficial e persistido no PostGIS local; não é demonstração limitada a fixtures.

## Condições de uso, limites e próximas etapas

A apresentação oficial permite consulta e download e informa limites dependentes do usuário. A responsabilidade pelos dados é atribuída ao gerador, com consistência realizada pelo SGB. Nas páginas/metadados consultados **não foi identificada licença explícita de redistribuição ampla**; disponibilidade pública não foi declarada como licença irrestrita. Mantêm-se atribuição RIMAS/SGB, URLs e origem. A aquisição local é limitada, sem contornar controles; publicação de conjuntos integrais exige esclarecer as condições aplicáveis com o SGB.

Limites: uma estação e um trimestre verificados; timeouts de séries ArcGIS; outras 27 estações não avaliadas temporalmente; marco, fuso, qualidade e equivalência bruto/tratado não confirmados. Não há consolidação diária, integração climática, operação de concessionária ou validação preditiva.

Próximas etapas: verificar gradualmente mais estações PI; confirmar com documentação técnica SGB o fuso, marco, instrumentos e tratamento; avaliar política diária derivada com rastreabilidade; investigar chuva real de estações compatíveis espacial/temporalmente e sua cobertura antes de qualquer vínculo; realizar validação histórica de qualidade e estabilidade do índice com dados suficientes, sem combinar automaticamente dados reais e sintéticos.

Arquivos desta fase: pacote `backend/app/ingestion/rimas/`, configuração opcional de URL no client SIAGAS, modelo/exportação `GroundwaterObservation`, migration 0006, campos aditivos nos schemas/API, testes/fixtures RIMAS e registro de model, volumes Compose, `frontend/src/RimasHistory.tsx`, ajustes em Pages/App, README, este documento e evidências em `output/rimas-*`. Mudanças pendentes das fases 10/11 foram preservadas. Separação recomendada: commit de base dessas fases, seguido de commit da Fase 12; nenhum commit automático foi criado.
