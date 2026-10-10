# Integração SIAGAS/SGB — Fase 11

## Estado da entrega e fonte

Implementado e validado em ambiente local com PostgreSQL/PostGIS em 10/10/2026: consulta oficial paginada, arquivo alternativo CSV/GeoJSON/JSON ArcGIS, validação, carga transacional idempotente, API existente, filtros de origem no mapa/lista e detalhes cadastrais. Piloto: **25 consultados, 25 importados, nenhum rejeitado**, município de Teresina/PI. Repetição do mesmo lote: **0 criados, 25 atualizados**. Não foi realizado deployment de produção.

SIAGAS é o Sistema de Informações de Águas Subterrâneas do Serviço Geológico do Brasil. Fontes oficiais verificadas:

- [Portal SIAGAS](https://siagasweb.sgb.gov.br/layout/).
- [Camada ArcGIS SIAGAS_MODDAD/FeatureServer/0](https://geoportal.sgb.gov.br/server/rest/services/hidrologia/SIAGAS_MODDAD/FeatureServer/0).
- [Endpoint de consulta](https://geoportal.sgb.gov.br/server/rest/services/hidrologia/SIAGAS_MODDAD/FeatureServer/0/query).
- [Apresentação e acesso público pelo SGB](https://www.sgb.gov.br/gestao-da-informacao-hidrogeologica).
- [Item do serviço](https://geoportal.sgb.gov.br/portal/sharing/rest/content/items/9bcd920625e34ebba97351c4ac82719c?f=pjson): acesso `public`; `licenseInfo`, `accessInformation` e copyright da camada estavam vazios. Acesso público foi confirmado, mas não foi identificada licença específica de redistribuição; não se afirma licença irrestrita. Preserve atribuição SGB/SIAGAS e confira as condições atuais antes de redistribuir em escala.

Metadados confirmados: `geometryType=esriGeometryPoint`, `sourceSpatialReference=4326`, `objectIdField=idt_ponto`, `supportsPagination=true`, `supportsOrderBy=true`, `maxRecordCount=1000`. Respostas JSON; também oferece GeoJSON/PBF. Não foi publicada uma quota de requisições por segundo nos metadados inspecionados. O cliente usa chamadas sequenciais, pausa de 250 ms, timeout de 30 s, até duas novas tentativas com backoff de 1/2 s para falhas transitórias. HTTP 429 respeita `Retry-After` numérico até 60 s; espera maior interrompe a execução. HTTP 401/403 não é repetido nem contornado. Erros ArcGIS no corpo JSON interrompem o processo.

`UPPER(str_uf)='PI'` e `UPPER(str_municipio)='TERESINA'` foram confirmados por consulta real. Nomes municipais da fonte têm caixa mista e acentos; use o nome com a grafia oficial. Strings SQL são escapadas; não há opção de fornecer SQL arbitrário. `--bbox WEST SOUTH EAST NORTH` é envelope geográfico 4326, aplicado na fonte e na validação. O envelope conservador do Piauí (-46.1 a -40.3; -11 a -2.5) rejeita pontos claramente externos; **não equivale a uma verificação por polígono administrativo oficial**.

## Arquitetura e persistência

O pacote `backend/app/ingestion/siagas/` reaproveita SQLAlchemy, schemas internos, models e endpoints existentes. A ingestão fica no backend para execução pelo mesmo ambiente Docker; não há ETL público anterior a duplicar. `client.py` comunica; `extract.py` armazena respostas; `mappings.py` define campos/unidades; `transform.py` normaliza; `validate.py` valida; `load.py` persiste; `cli.py` coordena.

Extração não grava no banco. Metadados, páginas e manifesto com fonte, seleção, lote e horário UTC ficam em `data/raw/siagas/<lote>/`. Registros normalizados e relatório ficam em `data/processed/siagas/`. Estes diretórios são dados locais ignorados pelo Git e montados no Docker. Sem `--load`, somente extrai e valida. Falha em qualquer página impede a carga; páginas já recebidas ficam disponíveis para diagnóstico. `extraction.json` completo somente é gravado após a conclusão.

Migration `0005_siagas_catalog.py`: adiciona `source_record_id` e `source_metadata JSONB` a `wells`, chave única `(source, source_record_id)` e permite `is_active=null` para operação desconhecida. **Valores booleanos existentes são preservados.** O contrato de resposta passa a aceitar `null` neste campo; clientes externos devem apresentar desconhecido, sem convertê-lo em inativo. Campos adicionais de proveniência são opcionais para cadastros anteriores. Downgrade com valores nulos é recusado pelo banco; exige resolução explícita do contrato, sem preencher falsamente os estados.

Identidade: UUIDv5 de `SIAGAS:<idt_ponto>`, código `SIAGAS-<idt_ponto>` e chave da fonte. Nome e coordenadas nunca definem identidade. Nome ausente usa somente rótulo explícito `SIAGAS <id>`. O loader valida o lote inteiro, trava a integração, verifica conflitos de UUID/código/chave e executa upsert protegido por `source=SIAGAS`, `data_classification=PUBLIC`. Conflito com qualquer outra origem aborta a transação. `created_at` permanece; `updated_at` registra atualização local. Não há delete, reset, associação de setor ou inserção de medições.

## Mapeamento e unidades

| Campo oficial | Destino/regra |
|---|---|
| `idt_ponto` | `source_record_id`, UUID estável e código; obrigatório |
| `str_nome_ponto` | `name`, com rótulo SIAGAS se ausente |
| `str_uf`, `str_municipio` | `state`, `municipality`; UF obrigatória, seleção municipal conferida |
| Geometria `x,y` | `location POINT`, longitude/latitude, SRID 4326 |
| `num_longitude_decimal`, `num_latitude_decimal` | Alternativa somente em CSV sem geometria, explicitamente 4326 |
| `num_profundidade` | `depth_m`, metros, opcional; negativos/não finitos rejeitados |
| `str_aquifero` | `source_metadata.aquifer` |
| `str_tipo_situacao` | `source_metadata.registry_status`, histórico; não determina operação atual |
| `str_uso_agua`, `str_natureza_ponto` | `declared_use`, `point_type` |
| `ne`, `nd` | `static_level_m`, `dynamic_level_m`, metros, somente descrição cadastral |
| `num_vazao_especifica` | Atributo bruto e unidade m³/h/m; **nunca vazão de produção** |
| `data_cadastro` | `registered_at` ISO UTC; ArcGIS fornece epoch em milissegundos |
| `data_perfuracao`, `data_instalacao`, demais atributos | Preservados em `source_metadata.attributes`; não são datas de monitoramento |
| Origem/extração | `source=SIAGAS`, `data_classification=PUBLIC`, `is_synthetic=false` derivado, URL, lote, horário, unidades e avisos |

Unidades de profundidade e níveis confirmadas nas fichas oficiais e no [relatório hidrogeológico SGB](https://rigeo.sgb.gov.br/jspui/bitstream/doc/5249/1/rel_hidro_RS_final.pdf), que distingue vazão e capacidade específica. [Ficha oficial com nomenclatura/unidades dos testes](https://siagasweb.sgb.gov.br/layout/detalhe_poco.php?ponto=3500051142). Os aliases ArcGIS sozinhos não definem unidades. Não houve scraping para extrair poços; o acesso aos registros utiliza exclusivamente o serviço de dados.

Níveis inválidos ou ND < NE ficam apenas nos atributos brutos, com valores normalizados nulos e avisos. Datas inválidas também recebem avisos. Ausência não vira zero. Geometria nula é rejeitada; coordenadas devem ser finitas e atender seleção. O serviço recebe `outSR=4326`; arquivos ArcGIS em 3857/102100/102113 podem ser convertidos por fórmula Web Mercator para WGS84. Outros SRIDs são recusados. GeoJSON deve seguir RFC 7946, Point, longitude/latitude 4326, sem CRS alternativo. Não há reprojeção arbitrária de datums.

## Comandos e piloto

Na raiz do repositório, com Docker:

```sh
docker compose up -d backend frontend
docker compose exec -T backend alembic upgrade head
# Extração e validação sem gravação (padrão):
docker compose exec -T backend python -m app.ingestion.siagas.cli --state PI --municipality Teresina --limit 25 --page-size 10 --raw-dir /data/raw/siagas --processed-dir /data/processed/siagas
# Extração, validação e carga transacional:
docker compose exec -T backend python -m app.ingestion.siagas.cli --state PI --municipality Teresina --limit 25 --page-size 10 --raw-dir /data/raw/siagas --processed-dir /data/processed/siagas --load
```

Use `--bbox -42.95 -5.30 -42.60 -4.90` para selecionar uma região; pode ser combinado com município. `--limit` padrão 25: aumentar exige decisão explícita; o tamanho das páginas nunca supera o metadado oficial. Ampliação preserva arquitetura e proteção de origem. A seleção é ordenada pelo identificador oficial; não é uma amostra estatística representativa.

Para repetir exatamente o lote piloto já recebido, sem nova consulta externa:

```sh
docker compose exec -T backend python -m app.ingestion.siagas.cli --input /data/raw/siagas/20261010T162313Z-41e2af8d/extraction.json --municipality Teresina --limit 25 --raw-dir /data/raw/siagas --processed-dir /data/processed/siagas --load
```

Uma nova extração atualiza os mesmos IDs e registra novo lote, sem duplicar poços. JSON de extração conserva a data original; exportação CSV/GeoJSON avulsa registra horário de ingestão do arquivo e não inventa data original de exportação. Para execução local a partir de `backend`, use `.venv/Scripts/python.exe -m app.ingestion.siagas.cli ...` (ou `.venv/bin/python` no Linux), após configurar conexão PostgreSQL por variáveis de ambiente. Nesta instalação o banco Docker usa porta **5433**, enquanto o default do backend local é 5432; a execução validada foi dentro do Docker.

## Fonte indisponível / arquivo oficial

Obtenha legalmente exportação no portal ou serviço oficial, copie para `data/raw/siagas/` e informe a URL original. Não use uma amostra inventada como arquivo oficial. CSV UTF-8 com cabeçalhos oficiais, vírgula como delimitador e ponto decimal, ou GeoJSON RFC 7946 com propriedades oficiais; JSON ArcGIS também é aceito. UF/município/limite/bbox continuam validados, e o identificador `idt_ponto` permanece obrigatório.

```sh
docker compose exec -T backend python -m app.ingestion.siagas.cli --input /data/raw/siagas/exportacao-oficial.geojson --source-url https://siagasweb.sgb.gov.br/layout/ --municipality Teresina --limit 25 --raw-dir /data/raw/siagas --processed-dir /data/processed/siagas --load
```

Registros rejeitados e motivos são registrados no relatório; válidos podem ser importados. Campos obrigatórios ausentes não são fabricados. O limite incide nos registros examinados, não somente nos aceitos; verifique rejeições antes de ampliar. Duplicata dentro do lote rejeita a ocorrência posterior. Falha de banco causa rollback da carga inteira.

## API, interface e verificação

Reutilizados: `/api/v1/wells`, `/wells/{id}`, `/measurements`, `/wells/{id}/risk`, `/wells/{id}/indicators`, `/dashboard/summary` e ranking existente. `/wells?source=SIAGAS` filtra origem exata; `source=SIMULATED` seleciona todos os sintéticos por classificação, mantendo busca, município, UF, setor, paginação e status. SIAGAS com status nulo não entra nos filtros booleanos de operação.

Visão Geral mostra total de cadastros, simulados, SIAGAS e quantidade avaliável na referência do motor; inclui data analítica. O total de medições permanece separado. O mapa mantém o layout e acrescenta origem, marcadores roxos quadrados e legenda SIAGAS. A lista também filtra origem. Detalhes mostram fonte oficial, cadastro histórico, aquífero, profundidade, níveis cadastrais, data de cadastro e extração; data original de atualização é desconhecida. No piloto não há séries operacionais; mapa/detalhe exibem **“Indicadores operacionais indisponíveis para este cadastro.”**, sem gráficos de outro poço. O motor retorna `status=INSUFFICIENT_DATA`, `score=null`, `classification=null`. Nenhum cadastro é atribuído a uma concessionária ou setor sintético.

Consultas SQL de verificação:

```sql
SELECT source, data_classification, count(*) FROM wells GROUP BY 1, 2;
SELECT count(*), count(DISTINCT source_record_id), min(ST_SRID(location)),
       bool_and(ST_IsValid(location)) FROM wells WHERE source='SIAGAS';
SELECT count(*) FROM well_sectors l JOIN wells w ON w.id=l.well_id WHERE w.source='SIAGAS';
SELECT count(*) FROM groundwater_measurements;
SELECT count(*) FROM operational_measurements;
SELECT count(*) FROM rainfall_measurements;
```

Esperado após piloto: 80 SIMULATED + 25 PUBLIC/SIAGAS = 105 cadastros; 25 IDs únicos, SRID 4326, geometrias válidas, zero vínculos SIAGAS; 58.400 + 58.400 + 14.600 = 131.400 medições. Checksums de conteúdo antes/depois em `output/siagas-before.json` e `output/siagas-after.json` verificam preservação integral dos simulados, setores, vínculos e medições.

## Testes e limites

```sh
docker compose exec -T -e RUN_POSTGIS_TESTS=1 backend python -m pytest -q -p no:cacheprovider
docker compose exec -T backend alembic check
docker compose exec -T frontend npm run build
docker compose config --quiet
```

Fixtures pequenas oficiais em `backend/tests/fixtures/siagas-*.json`, obtidas da camada em 10/10/2026; não incluem dados de proprietários/contatos. Testes unitários não acessam a rede. Cobrem parsing, campos ausentes, seleção, unidades, coordenadas, SRID, duplicatas, paginação, erros externos e arquivos alternativos. Integração PostGIS usa schema temporário/rollback e confirma idempotência, proteção de outras origens, proveniência, API, insuficiência e preservação do conteúdo sintético. Interface é verificada interativamente, complementada por TypeScript/build; não há suíte automatizada de frontend configurada.

**Limitado:** cadastro histórico sem data de teste/atualização suficientemente definida, qualidade e preenchimento variáveis, envelope geográfico sem fronteira administrativa oficial, ausência de licença específica nos metadados, sem séries de produção/demanda/bombeamento/população. `data_cadastro` não significa atualização atual ou data de medição. Piloto não demonstra validação hidrogeológica nem operacional em produção.

**Planejado:** verificação espacial por malha administrativa oficial, revisão técnica da consistência hidrogeológica, observabilidade/cache para maiores volumes e eventual associação operacional mediante evidências independentes. Próximas integrações RIMAS e clima exigem identificar estações/séries, unidades, datas, qualidade, licenças e proveniência por observação, sem reaproveitar dados sintéticos como evidência real. Não foram implementadas nesta fase.
