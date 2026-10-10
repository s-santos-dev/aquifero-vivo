# Arquitetura inicial

Monorepo com serviços independentes: API FastAPI, cliente React/Vite e PostgreSQL com PostGIS. O Compose é destinado ao desenvolvimento local, com portas publicadas apenas em loopback e volume persistente para o banco.

O backend usa Pydantic Settings para configuração, SQLAlchemy 2/GeoAlchemy2 para sessões e mapeamento e Alembic para migrações. A primeira migração garante a extensão PostGIS; a segunda cria as entidades do modelo inicial. Models ORM e schemas Pydantic permanecem em pacotes separados. Não há criação automática de tabelas pela aplicação: o processo de inicialização usa exclusivamente `alembic upgrade head`.

O serviço do backend depende do healthcheck do banco e usa `restart: on-failure`: caso o PostgreSQL ainda esteja concluindo sua inicialização quando o Alembic tentar conectar, o serviço repete a inicialização automaticamente.

`GET /health` indica que o processo da API está respondendo; não verifica disponibilidade do banco. O Compose verifica o banco separadamente com `pg_isready`.

O frontend usa TanStack Query para consultar a API, React Leaflet para o mapa e Recharts para o histórico de medições. Os indicadores são calculados sob demanda em `backend/app/indicators/` e expostos pela API sem tabelas adicionais. Consulte [indicators.md](indicators.md) para fórmulas e limites.

Pandas, GeoPandas, NumPy e Scikit-learn são dependências opcionais do backend (`data`), instaladas na imagem Docker. Há cálculo multicritério experimental em `app/risk/`, com ingestão cadastral SIAGAS na Fase 11 e sem ML. Dados locais ficam fora do Git; as pastas são preservadas com `.gitkeep`.

A fase 9 agrega ranking com leitura em lote, alertas derivados e sugestões determinísticas no mesmo pacote de risco. Veja [prioritization.md](prioritization.md). Não grava nas tabelas de avaliações/alertas.
