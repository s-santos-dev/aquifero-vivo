# Modelo de dados inicial

O modelo usa PostgreSQL com PostGIS, SQLAlchemy 2 para o mapeamento ORM e Alembic para evolução do schema. Todas as entidades têm `id` UUID, `created_at` e `updated_at` com fuso horário. As geometrias usam WGS 84 (`SRID 4326`), com longitude antes da latitude nos contratos GeoJSON.

Os models ORM ficam em `backend/app/models`; os contratos Pydantic de criação e leitura ficam separados em `backend/app/schemas`. Esta etapa somente persiste avaliações, fatores e alertas. Ela não calcula risco nem define um motor de risco.

As três tabelas de medições possuem `data_classification` obrigatório (`REAL`, `PUBLIC` ou `SIMULATED`). Os schemas Pydantic internos e a API normal aceitam todas essas origens, sempre exibindo a classificação. A resposta deriva `is_synthetic` dessa classificação. O simulador normaliza seu dataset nos mesmos schemas antes de gravar.

A migration `0004` acrescenta `source` e `data_classification` aos poços, setores e vínculos, preservando cadastros anteriores como `UNKNOWN`. Acrescenta também `dynamic_level_m` às medições subterrâneas e `daily_demand_m3`, `utilization`, `operational_failure` às operacionais. `water_level_m` é o nível estático usado pelo simulador. As geometrias e relações existentes permanecem inalteradas.

A migration `0003` não tenta adivinhar a origem de registros anteriores. Se alguma tabela de medições já contiver linhas, ela interrompe a atualização com uma mensagem explícita para que a classificação seja feita por um procedimento de migração de dados revisado. Em um banco novo, as colunas são criadas diretamente como obrigatórias. Essa decisão evita que dados sintéticos legados recebam silenciosamente o rótulo `REAL`.

## Entidades

### `Well` (`wells`)

Representa um poço monitorado. `code` é a identificação de negócio única; `location` é um `POINT` obrigatório; município, UF, profundidade e estado ativo complementam o cadastro.

Um poço possui muitas medições subterrâneas, medições operacionais, associações com setores, avaliações de risco e alertas. A exclusão do poço remove esses registros dependentes.

### `GroundwaterMeasurement` (`groundwater_measurements`)

Registra uma observação hidrogeológica de um poço em `measured_at`. O nível d'água é obrigatório e não negativo; temperatura, pH, condutividade e origem são opcionais. Cada medição pertence a exatamente um `Well`.

### `RainfallMeasurement` (`rainfall_measurements`)

Registra precipitação não negativa em uma posição (`POINT`) e instante. Pode indicar período de acumulação, estação e origem. A associação a `ServiceSector` é opcional, pois dados pluviométricos podem chegar antes da classificação territorial; se um setor for removido, a medição e sua geometria são preservadas.

### `OperationalMeasurement` (`operational_measurements`)

Registra as condições de operação de um poço em um instante: vazão, volume bombeado, horas de funcionamento, status e origem. Grandezas quantitativas, quando informadas, não podem ser negativas. Cada registro pertence a um `Well`.

### `ServiceSector` (`service_sectors`)

Representa uma área operacional de abastecimento. Tem código único, nome, descrição e limite territorial obrigatório em `MULTIPOLYGON`. Relaciona-se a poços através de `WellSector` e pode agrupar medições de chuva.

### `WellSector` (`well_sectors`)

É a entidade associativa entre `Well` e `ServiceSector`. Além das duas chaves estrangeiras, guarda `valid_from` e `valid_to`, permitindo preservar mudanças de setor ao longo do tempo. `valid_to`, quando preenchido, deve ser posterior a `valid_from`; a combinação poço, setor e início é única.

### `RiskAssessment` (`risk_assessments`)

Persiste o resultado de uma avaliação de risco para um poço. Contém instante, pontuação entre 0 e 100, nível (`low`, `medium`, `high` ou `critical`), versão da metodologia, validade opcional e observações. Uma avaliação agrega seus `RiskFactor` e pode ser referenciada por alertas.

Não há nesta entrega lógica para produzir esses valores; a tabela é o contrato de persistência para uma implementação posterior.

### `RiskFactor` (`risk_factors`)

Detalha um componente de uma avaliação. Guarda código e nome, valor bruto, valor normalizado, peso, contribuição e detalhes JSON opcionais. O código é único dentro da avaliação. A exclusão da avaliação remove seus fatores.

### `Alert` (`alerts`)

Representa um evento que demanda atenção para um poço. Guarda tipo, severidade (`info`, `warning` ou `critical`), status (`open`, `acknowledged` ou `resolved`), conteúdo e instantes do ciclo de vida. Pode referenciar a `RiskAssessment` que lhe deu origem; essa referência é anulada se a avaliação for removida, preservando o histórico do alerta.

## Relacionamentos

```text
Well 1 ─── N GroundwaterMeasurement
Well 1 ─── N OperationalMeasurement
Well 1 ─── N WellSector N ─── 1 ServiceSector
ServiceSector 1 ─── N RainfallMeasurement (associação opcional no lado da medição)
Well 1 ─── N RiskAssessment 1 ─── N RiskFactor
Well 1 ─── N Alert N ─── 0..1 RiskAssessment
```

As relações são bidirecionais no SQLAlchemy por meio de `relationship(..., back_populates=...)`. Dependentes estritos usam `CASCADE`; referências históricas opcionais usam `SET NULL`.

## Índices e consultas esperadas

- GiST em `wells.location`, `rainfall_measurements.location` e `service_sectors.boundary` para proximidade, contenção e interseção espacial.
- Índices temporais simples em `measured_at`/`assessed_at` para recortes globais por período.
- Índices compostos `(well_id, measured_at)` nas séries subterrânea e operacional.
- Índice composto `(service_sector_id, measured_at)` na chuva.
- Índices `(well_id, assessed_at)` em avaliações e `(well_id, triggered_at)` em alertas.
- Índice `(status, triggered_at)` para filas de alertas e índice de nível de risco para filtros operacionais.
- Índices nas chaves estrangeiras que não são prefixo de outro índice útil.

## Migrações

`0001_enable_postgis.py` habilita PostGIS. `0002_initial_data_model.py` cria as nove tabelas, restrições, chaves estrangeiras e índices. O downgrade de `0002` remove as tabelas na ordem inversa de dependência, mas preserva a extensão PostGIS, que pode ser compartilhada por outros objetos do banco.
