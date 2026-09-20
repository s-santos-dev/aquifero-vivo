# Arquitetura inicial

Monorepo com serviços independentes: API FastAPI, cliente React/Vite e PostgreSQL com PostGIS. O Compose é destinado ao desenvolvimento local, com portas publicadas apenas em loopback e volume persistente para o banco.

O backend usa Pydantic Settings para configuração, SQLAlchemy 2/GeoAlchemy2 para sessões e mapeamento e Alembic para migrações. A primeira migração garante a extensão PostGIS; a segunda cria as entidades do modelo inicial. Models ORM e schemas Pydantic permanecem em pacotes separados. Não há criação automática de tabelas pela aplicação: o processo de inicialização usa exclusivamente `alembic upgrade head`.

O serviço do backend depende do healthcheck do banco e usa `restart: on-failure`: caso o PostgreSQL ainda esteja concluindo sua inicialização quando o Alembic tentar conectar, o serviço repete a inicialização automaticamente.

`GET /health` indica que o processo da API está respondendo; não verifica disponibilidade do banco. O Compose verifica o banco separadamente com `pg_isready`.

O frontend usa TanStack Query para consultar a saúde da API e Tailwind CSS para estilos. React Leaflet e Recharts estão instalados para etapas futuras, sem mapas ou gráficos nesta entrega.

Pandas, GeoPandas, NumPy e Scikit-learn são dependências opcionais do backend (`data`), instaladas na imagem Docker. Não há coleta SIAGAS, modelos de ML ou cálculo de risco. Dados locais ficam fora do Git; as pastas são preservadas com `.gitkeep`.
