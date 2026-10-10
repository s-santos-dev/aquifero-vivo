# Fase 13 — precipitação pública INMET

Piloto real adquirido e carregado em **10/10/2026**, separado da chuva sintética e do motor de risco. **INMET A237, Caxias/MA: 2.160 acumulados horários válidos, 90 dias UTC completos, 01/01/2025–31/03/2025, zero rejeições, duplicatas ou lacunas.** Total descritivo do trimestre: **683,2 mm**. É uma fonte regional para comparação exploratória; não é uma medição de precipitação na RETE ou sobre seu aquífero.

## Investigação anterior à carga

Foram lidos README, documentação RIMAS, modelos, pipelines SIAGAS/RIMAS e migrations 0001–0006. Nenhum AGENTS.md aplicável foi encontrado nas pastas do projeto/ancestrais consultados; o arquivo dentro de `frontend/node_modules/recharts` não rege o código da aplicação. As alterações pendentes das fases anteriores foram preservadas.

| Fonte | Método, disponibilidade e limites verificados | Decisão |
| --- | --- | --- |
| [INMET — arquivos anuais automáticos](https://portal.inmet.gov.br/dadoshistoricos/) | Download oficial ZIP por ano; link 2025 presente. Uma CSV por estação, identificação e coordenadas no cabeçalho, dados horários UTC. Sem autenticação no download normal utilizado. Sem filtro remoto por estação/período nem paginação. | Selecionada; preserva-se ZIP inteiro e CSV original, processando somente um trimestre/estação. |
| [BDMEP](https://bdmep.inmet.gov.br/) e [descrição institucional](https://portal.inmet.gov.br/servicos/bdmep-dados-historicos) | Aplicação JavaScript; serviço de séries diárias de estações convencionais. Não foi confirmado um endpoint anônimo de exportação nem adquirido arquivo convencional nesta fase. | Não se presume acesso público programático. Disponibilidade da estação convencional de Teresina continua não verificada; não é declarada inexistente. |
| [NASA GPM/IMERG](https://gpm.nasa.gov/data/imerg), [acesso](https://gpm.nasa.gov/data/sources), [política](https://gpm.nasa.gov/data/policy) | Produto de estimativa multisatélite; NASA documenta diferentes serviços e processamento. PPS requer registro. Nenhuma célula, versão, arquivo, credencial ou série do trimestre foi adquirida. | Alternativa futura; não necessária para este piloto com observações INMET. Não se presume endpoint sem autenticação nem equivalência com pluviômetro. |

Requisições diretas ao ZIP por Python/httpx/curl falharam por desconexão, sem resposta útil. O download normal do link **ANO 2025 (AUTOMÁTICA)** pelo navegador funcionou, sem login, CAPTCHA, alteração de segurança ou contorno de proteção. O CLI aceita esse ZIP via `--file`; a extração direta continua disponível, mas **não foi validada com sucesso contra a rede real neste ambiente**. Ela foi testada offline com resposta HTTP oficial reduzida. Não se faz scraping de valores ou gráficos.

Inventário das estações automáticas do arquivo 2025 dentro de 200 km da RETE, calculado com Haversine (raio terrestre médio 6.371,0088 km); inspeção das horas do trimestre e da virada seguinte:

| Código | Local | Distância aproximada | Precipitação no arquivo para o trimestre |
| --- | --- | ---: | --- |
| A312 | Teresina/PI | 5,93 km | **Todos os 2.160 intervalos necessários vazios** |
| A237 | Caxias/MA | 67,18 km | Todos os intervalos necessários disponíveis |
| A376 | Campo Maior/PI | 76,59 km | Vazia |
| A377 | Angical do Piauí/PI | 111,63 km | Vazia |
| A335 | Piripiri/PI | 143,37 km | Disponível na inspeção preliminar, não importada |
| A361 | Castelo do Piauí/PI | 145,47 km | Vazia |
| A206 | Chapadinha/MA | 161,65 km | Disponível na inspeção preliminar, não importada |
| A311 | Floriano/PI | 187,43 km | Vazia |
| A363 | Valença do Piauí/PI | 188,58 km | Disponível na inspeção preliminar, não importada |
| A222 | Colinas/MA | 190,33 km | Vazia |

Inventário local em `data/raw/climate/research/nearby-inventory.json`. Não é um inventário de todas as fontes pluviométricas regionais. “Disponível” na inspeção das alternativas não certifica qualidade científica e não afirma carga dessas séries. A ausência de valores da A312 foi também processada pelo pipeline: **0 observados, 2.160 valores ausentes, 0 dias completos**; código de saída 2 e **nenhuma carga**. Evidência em [climate-a312-unavailable.json](../output/climate-a312-unavailable.json). Não foi necessário mudar o período; foi explicitamente escolhida outra estação INMET.

## Geografia e interseção com RIMAS

| Local | Latitude | Longitude | Identidade |
| --- | ---: | ---: | --- |
| INMET Caxias/MA | −4,82138888 | −43,34361110 | A237 |
| RIMAS RETE, Teresina/PI | −5,088056 | −42,799444 | 2200034952 |

Caxias: altitude original 84,85 m, fundação 13/07/2008, estação automática. Essas informações descrevem o cadastro, não certificam estabilidade instrumental. `A237` é o identificador textual publicado no campo `CODIGO (WMO):`; não se infere um número internacional WMO distinto.

Distância final da API: **67,170592246 km**, com `ST_Distance` sobre `geography` PostGIS, elipsoide WGS84. A diferença em relação à distância Haversine decorre do método esférico/elipsoidal. São coordenadas geográficas publicadas, armazenadas em EPSG:4326 para consulta territorial; **o CSV não declara explicitamente o datum original**, limitação preservada nos metadados. Não se atribui precisão hidrogeológica aos muitos dígitos da distância.

Interseção por **rótulos de data civil**: janeiro–março de 2025, 90 dias; RIMAS contém 91 leituras, incluindo duas em 28/01, em horários irregulares e fuso desconhecido. INMET usa intervalos horários UTC; o gráfico climático usa dias UTC. Essa interseção de datas **não confirma alinhamento de instantes**. A distância, diferenças locais de chuva e ausência de representatividade espacial aprovada impedem atribuição automática à RETE. A consulta não cria FK entre poço e estação nem vínculos com setores sintéticos.

## Aquisição e rastreabilidade

Arquivo: [ZIP oficial 2025](https://portal.inmet.gov.br/uploads/dadoshistoricos/2025.zip), **90.898.634 bytes**. Formato CSV Latin-1 com `;`, decimal com vírgula, 8 linhas cadastrais e uma linha de nomes de colunas. Inclui data, hora UTC, precipitação, pressão, radiação, temperaturas, umidade e vento. Apenas precipitação é normalizada; as demais células permanecem em `original_row`, sem interpretação ou uso operacional.

Lote carregado: `20261010T171834Z-02a03add`, aquisição registrada `2026-10-10T17:18:34.874668+00:00`. No caminho manual, esse horário é a **incorporação do arquivo ao lote**; cabeçalhos HTTP e hora de transferência do navegador não são recuperados artificialmente. `response_headers={}` registra essa limitação.

- SHA-256 ZIP: `14988d0b736ba969b48881589f602f3a6d7e97b95bd1de934456851fdac2cb89`.
- Membro: `2025/INMET_NE_MA_A237_CAXIAS_01-01-2025_A_31-12-2025.CSV`.
- SHA-256 CSV original completo: `439fce282060d45d44b1101c39f25ea3b88e79eb9c68dfa0378410d5428c3e26`.

Cada lote tem diretório exclusivo, `annual.zip`, `station.csv`, `manifest.json`; falhas de extração têm `failure.json`. Nenhum lote anterior é sobrescrito. Reprocessamento verifica ambos os checksums e compara o membro ZIP com a CSV. Trata-se de imutabilidade do fluxo, não armazenamento WORM ou assinatura de autenticidade. SHA-256 prova integridade dos bytes adquiridos, não certifica instrumento ou fonte de um arquivo manual adulterado.

Timeout 60 s; até duas repetições de falhas de transporte/5xx, espera 1/2 s. HTTP 403/404/429 interrompem, sem contorno ou repetição de limite. Redirecionamento fora do domínio institucional é rejeitado. Limites locais: ZIP 150 MiB, CSV 5 MiB, estação com código `A` e três dígitos, período de até 366 dias no mesmo ano. **31/12 não é suportado nesta versão**, pois o intervalo final requer 01/01 do arquivo seguinte; a seleção é recusada, sem produzir total incompleto. Limites institucionais de requisições não foram publicados nas páginas verificadas; estes são limites defensivos do piloto, não quotas oficiais. Nenhuma coleta em massa recorrente foi configurada.

## Tempo, unidade, validação e derivação diária

Campo oficial: `PRECIPITAÇÃO TOTAL, HORÁRIO (mm)`. O [glossário oficial INMET](https://portal.inmet.gov.br/glossario/nublado) define precipitação automática como total na **última hora anterior à mensagem**. `Hora UTC` é explícito no arquivo. Cada leitura em `t` representa o intervalo anterior de uma hora; preservam-se `interval_start=t−1h`, `interval_end=t`, data/hora/unidade/valor originais.

Para o dia UTC D, somam-se leituras de D **01:00 até D+1 00:00**, somente quando existem exatamente 24 intervalos distintos observados. O horário D 00:00 pertence ao dia anterior e é excluído. O piloto persistiu **2025-01-01T01:00Z até 2025-04-01T00:00Z**: cobre integralmente os dias UTC 01/01–31/03. Não se usa soma ingênua dos rótulos 00–23 da CSV como dia físico. Não se converte o fuso RIMAS nem se declara alinhamento local.

Regra versionada: `INMET_PREVIOUS_HOUR_24_INTERVALS_UTC_V1`. Diários são calculados na consulta, sem substituir os horários originais. Resposta diária contém IDs contribuintes, horas observadas/esperadas, estado, regra, unidade, qualidade e timezone. Uma única hora ausente/ambígua invalida o total: `value_mm=null`, `INSUFFICIENT_DATA`. Não há soma parcial apresentada como completa, interpolação, preenchimento, média de duplicatas ou transporte de valores entre dias.

Validação: contrato exato do cabeçalho; identidade oficial; coordenadas finitas e dentro dos limites geográficos; datas civis reais; horas cheias UTC 00–23; valores finitos, não negativos, capacidade decimal `NUMERIC(12,4)` e precisão de até quatro casas. Identidades distintas usam estação + timestamp de fim do intervalo; o arquivo não oferece ID externo de cada observação (`source_record_id=null`). UUIDs locais são determinísticos e não são identificadores oficiais novos.

| Situação | Persistência e cálculo |
| --- | --- |
| Zero observado | `OBSERVED`, valor 0; contribui ao dia completo |
| Campo vazio / sentinela −9999 ou −9999,0 | `MISSING`, valor null, célula original preservada; não contribui |
| Linha ausente | Nenhum registro fabricado; hora/dia ausente aparece na consulta |
| Valor/data/contrato rejeitado | Relatório com linha original e motivo; lote com rejeições impede carga |
| Qualidade não fornecida | `quality_status=NOT_PROVIDED`, mesmo com valor válido; validação estrutural não certifica qualidade instrumental |

Duplicatas idênticas na mesma aquisição são contabilizadas e consolidadas por identidade; duplicatas conflitantes são todas rejeitadas. Revisões divergentes de observações/cadastro já persistidos abortam a transação e exigem análise explícita. Ausência não vira zero; desconhecimento de qualidade não é interpretado como ausência de chuva.

Acumulados de 7/30/60/90 dias exigem **100% de dias completos**, inclusive os dias anteriores à janela solicitada. Em 31/03/2025: **2,0 / 360,0 / 503,0 / 683,2 mm**, respectivamente. Antes de haver histórico suficiente retornam `INSUFFICIENT_DATA`. Não se calculam normal climatológica, índice oficial de seca, previsão ou recarga.

## Persistência, arquitetura e preservação

Pacote `backend/app/ingestion/climate/`: `client.py`, `extract.py`, `transform.py`, `validate.py`, `load.py`, `cli.py`, `__init__.py`. Não se criaram wrappers ou mappings desnecessários. O fluxo segue SIAGAS/RIMAS, utiliza `SessionLocal` e padrões de proveniência/UUID; parsing e tempo climáticos exigem regras próprias. Consultas e diários em `backend/app/climate/`; modelos e schemas em `backend/app/models/climate.py`, `backend/app/schemas/climate.py`.

Migrations **0007** (duas tabelas e índices) e **0008** (constraint explícita contra observado null sob lógica SQL). 0008 foi acrescentada após aplicar 0007; **nenhuma migration aplicada foi reescrita**. `climate_stations` tem identidade INMET, nome/tipo, geometria, metadados oficiais e auditoria. `rainfall_observations` tem FK somente da estação climática, timestamp UTC, valor nullable, mm, origem, disponibilidade, JSONB original/proveniência e auditoria. Não há FK para setores ou medições sintéticas.

Loader retransfoma/verifica a CSV antes de escrever, impede lotes sem observados, verifica conflitos antes de inserts e usa os advisory locks dos loaders público/sintético em ordem fixa. Reimportação idêntica mantém inclusive auditoria e a proveniência da primeira aquisição. O CLI é dono da transação; qualquer exceção reverte toda a carga.

Snapshots ordenados por ID calculam SHA-256 de **todo o conteúdo** das dez tabelas anteriores, incluindo auditoria, geometrias e JSONB. Antes/depois da carga e reimportação coincidiram. Também há evidência externa antes da migration/carga em [climate-before.json](../output/climate-before.json), relatório [climate-import.json](../output/climate-import.json), reimportação [climate-reimport.json](../output/climate-reimport.json) e estado final em [climate-after.json](../output/climate-after.json).

| Conteúdo preservado | Quantidade |
| --- | ---: |
| Poços sintéticos / públicos SIAGAS | 80 / 26 |
| Setores / vínculos | 20 / 80 |
| Medições subterrâneas sintéticas | 58.400 |
| Medições operacionais sintéticas | 58.400 |
| Medições de chuva sintética | 14.600 |
| Total de medições sintéticas | **131.400** |
| Observações reais RIMAS | **91** |

Nenhuma escrita ocorre no motor de risco, pesos, relógio de referência, simulador ou séries anteriores. A RETE continua com risco insuficiente. Acrescentados somente **1 estação climática e 2.160 observações INMET**. Não foi executado reset do banco.

## Comandos reproduzíveis

```sh
docker compose up -d backend frontend
docker compose exec -T backend alembic upgrade head

# Aquisição HTTP oficial, quando o serviço responder; padrão somente validação
docker compose exec -T backend python -m app.ingestion.climate.cli --station A237 --from 2025-01-01 --to 2025-03-31

# Caminho utilizado: baixar 2025.zip normalmente no portal e copiá-lo ao diretório montado
docker compose exec -T backend python -m app.ingestion.climate.cli --station A237 --from 2025-01-01 --to 2025-03-31 --file /data/raw/climate/research/2025.zip --load

# Reprocessar lote efetivamente carregado, offline e idempotente
docker compose exec -T backend python -m app.ingestion.climate.cli --batch /data/raw/climate/20261010T171834Z-02a03add --load

# Verificar ausência da A312; termina com código 2, sem carga
docker compose exec -T backend python -m app.ingestion.climate.cli --station A312 --from 2025-01-01 --to 2025-03-31 --file /data/raw/climate/research/2025.zip
```

Resultados processados têm nomes exclusivos em `data/processed/climate/`. Dados brutos/processed ficam ignorados pelo Git. Fixture versionada `backend/tests/fixtures/inmet-a237.csv`: 25 linhas horárias oficiais inalteradas, de 01/01 00:00 a 02/01 00:00, mais cabeçalho; somente 24 representam o primeiro dia UTC. Manifesto distingue checksum da fixture e ZIP original. Testes ampliam artificialmente a duração **apenas em memória para testar cobertura**, nunca para criar série pública ou fixture apresentada como oficial.

## API e exemplos reais

Novas rotas, com schemas OpenAPI, máximo 100 itens por página; contratos anteriores preservados:

```text
GET /api/v1/climate/stations?q=A237&page=1&page_size=20
GET /api/v1/climate/stations/62d9510e-a8f3-5f7b-88be-453fe8e1aca4
GET /api/v1/climate/stations/62d9510e-a8f3-5f7b-88be-453fe8e1aca4/rainfall?start=2025-01-01&end=2025-03-31&resolution=daily&page_size=100
GET /api/v1/climate/stations/62d9510e-a8f3-5f7b-88be-453fe8e1aca4/rainfall?start=2025-01-01&end=2025-01-01&resolution=hourly&page_size=24
GET /api/v1/climate/stations/62d9510e-a8f3-5f7b-88be-453fe8e1aca4/indicators?reference_date=2025-03-31
GET /api/v1/wells/1b2e8ad0-1c88-5d1d-a102-2603a45a2026/nearby-climate?radius_km=100&start=2025-01-01&end=2025-03-31
```

Histórico: `start`/`end` inclusivos por dia UTC, até 366 dias; padrão últimos 90 dias importados. `resolution=daily` apresenta dias sem observação como null. Cada página diária busca no máximo 100×24 intervalos; hourly pagina as observações. Summary da estação usa agregação SQL e distingue registros, ausentes explícitos e horas sem registro. Cobertura histórica é disponibilidade da **série importada**, não afirma disponibilidade de toda a fonte. `coverage.scope=page` no histórico diário; o frontend calcula cobertura do período após buscar até quatro páginas limitadas. Nearby aceita raio até 500 km e período completo opcional; compara em PostGIS, com paginação, período e cobertura solicitados. Limites incompatíveis retornam 422; identidade inexistente retorna 404.

Exemplo real de indicador diário: **21/03/2025, 82,4000 mm, 24/24 horas, COMPLETE**, qualidade não fornecida, UTC. Evidências das respostas em [climate-api.json](../output/climate-api.json) e [climate-daily.json](../output/climate-daily.json). Fora da janela importada, totais e indicadores permanecem insuficientes, sem concluir ausência de precipitação na fonte.

## Frontend e validação

`frontend/src/ClimateHistory.tsx` integra-se ao histórico RIMAS, na seção **Precipitação próxima — dados públicos**. Seleção de estação/período, origem INMET, coordenadas, distância, cobertura, gráfico Recharts de barras sem preenchimento, tabela e lista de dias incompletos. Painel RIMAS permanece separado, em metros, com 91 observações e fuso desconhecido. Datas selecionadas independentemente em cada painel são explicitamente exibidas; não há correlação ou alinhamento científico automático. O layout existente foi preservado.

Inspeção real no navegador com API/PostGIS: estação/identidade/origem/distância, 90/90 dias, gráfico, período e tabela; consulta fora da importação (01–02/04) mostra 0/2 completos e insuficiência. Interrupção controlada do backend demonstrou a mensagem de erro do histórico; o serviço foi reiniciado. Período invertido foi recusado na interface. Evidências em [climate-frontend.png](../output/climate-frontend.png), [climate-frontend-missing.png](../output/climate-frontend-missing.png) e [climate-frontend-error.png](../output/climate-frontend-error.png). A verificação visual foi realizada, além do build.

Backend offline cobre leitura/contrato, identidade, coordenadas, unidades, datas, sentinelas, valores negativos/não finitos, duplicatas, integridade de checksums, erros HTTP/timeout/vazio/formato e limites, agregação estrita e ausência. Testes PostGIS usam schema/transação isolados, verificando persistência, constraint, idempotência, proveniência, integridade das tabelas anteriores, filtros/paginação/404/422, associação geográfica e recusa de atribuição ao risco. Comandos:

```sh
docker compose exec -T -e RUN_POSTGIS_TESTS=1 backend python -m pytest -q -o cache_dir=/tmp/climate-final-pytest-cache --basetemp=/tmp/climate-final-test-temp
docker compose exec -T backend alembic check
docker compose exec -T backend alembic current
docker compose exec -T backend alembic upgrade head --sql
docker compose exec -T frontend npm run build
docker compose config --quiet
```

Resultado final: **234 testes backend aprovados, incluindo PostGIS (42 adicionais aos 192 anteriores)**, registrados em [climate-validation.json](../output/climate-validation.json) e [climate-tests.txt](../output/climate-tests.txt). Alembic em 0008 e sem operações pendentes; SQL offline das migrations compilado; TypeScript/Vite e Compose válidos; carga/reimportação reais executadas. Dois avisos de depreciação Starlette/httpx/anyio preexistentes não representam falhas climáticas. O frontend foi validado por build e inspeção manual de navegador; não se adicionou framework de testes de componentes.

## Uso, ciência e próximas etapas

O INMET disponibiliza o download oficial; não foi localizada licença explícita para redistribuição ampla do ZIP anual nas páginas consultadas. Avisos de uso com atribuição em boletins específicos **não foram generalizados como licença de todo o arquivo**. Mantêm-se atribuição INMET, URL, arquivo original, checksums e extratos mínimos de teste. Arquivos integrais são locais e ignorados pelo Git; publicação massiva exige esclarecer condições aplicáveis com o INMET. A disponibilidade pública e a ausência de login não equivalem a licença irrestrita. A política NASA rege seus próprios produtos e não o INMET.

Conceitos distintos:

- **Chuva simulada**: 14.600 medições produzidas pelo gerador em setores fictícios; não são observações INMET.
- **Observação de estação**: medida pontual de pluviômetro, aqui acumulado horário INMET; qualidade instrumental por linha não fornecida.
- **Estimativa de satélite**: estimativa espacial/temporal por algoritmo/versão, como IMERG; não foi importada nem apresentada como estação.
- **Indicador derivado**: soma documentada de intervalos/dias completos com IDs de origem e regra; não é uma nova medição nem normal climatológica.
- **Inferência de recarga**: exige modelo/método hidrogeológico validado, outras variáveis e evidências; não é calculada a partir dessas somas ou da proximidade.

Limitações: uma estação regional, distância de 67 km, três meses, UTC distinto de fuso RIMAS desconhecido, datum cadastral não explícito, sem flags instrumentais, alternativa convencional local não verificada, aquisição HTTP real sem sucesso neste ambiente, fim de ano não suportado. Cobertura estrutural completa não prova representatividade territorial, precisão do instrumento ou ausência de viés. Não há normal climatológica, classificação oficial de seca, inferência causal, tempo de resposta, modelo de recarga, integração operacional ou mudanças no risco.

Próximas etapas: investigar convencional local e outras redes institucionais por mecanismos autorizados; verificar A312 e causas de indisponibilidade com INMET; confirmar datum/instrumento/qualidade e condições de redistribuição; ampliar gradualmente histórico e suporte a virada anual; avaliar representatividade espacial e alinhamento temporal com especialistas antes de qualquer política de associação ou uso no risco. IMERG requer escolher produto/versão/célula e acesso documentado antes de outra ingestão.
