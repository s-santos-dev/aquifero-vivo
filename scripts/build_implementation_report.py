from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf" / "documentacao_implementacao_aquifero_vivo.pdf"


def p(text, style):
    return Paragraph(text, style)


def page_number(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D9E7E2"))
    canvas.line(2 * cm, 1.45 * cm, A4[0] - 2 * cm, 1.45 * cm)
    canvas.setFillColor(colors.HexColor("#527069"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(2 * cm, 1.0 * cm, "AQUIFERO VIVO - DOCUMENTACAO DE IMPLEMENTACAO")
    canvas.drawRightString(A4[0] - 2 * cm, 1.0 * cm, f"Pagina {doc.page}")
    canvas.restoreState()


def status_table(rows, styles):
    data = [[p("Item", styles["tablehead"]), p("Situacao", styles["tablehead"]), p("Evidencia / observacao", styles["tablehead"])]]
    for item, status, note in rows:
        tone = "#167260" if status == "Implementado" else "#A05A00" if status == "Parcial" else "#B42318"
        data.append([p(item, styles["cell"]), p(f'<font color="{tone}"><b>{status}</b></font>', styles["cell"]), p(note, styles["cell"])])
    table = Table(data, colWidths=[4.0 * cm, 2.65 * cm, 8.55 * cm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5D50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7E4E0")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FBFA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def bullet(text, styles):
    return Paragraph(f"<bullet>&bull;</bullet>{text}", styles["body"])


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ss = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("title", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=27, leading=32, textColor=colors.HexColor("#0B5D50"), alignment=TA_CENTER, spaceAfter=14),
        "subtitle": ParagraphStyle("subtitle", parent=ss["Normal"], fontSize=11.5, leading=17, textColor=colors.HexColor("#527069"), alignment=TA_CENTER),
        "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=colors.HexColor("#0B5D50"), spaceBefore=10, spaceAfter=9),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=colors.HexColor("#167260"), spaceBefore=10, spaceAfter=5),
        "body": ParagraphStyle("body", parent=ss["BodyText"], fontSize=9.6, leading=14.2, textColor=colors.HexColor("#243B36"), spaceAfter=6),
        "small": ParagraphStyle("small", parent=ss["BodyText"], fontSize=8.3, leading=11.5, textColor=colors.HexColor("#527069"), spaceAfter=5),
        "tablehead": ParagraphStyle("tablehead", parent=ss["BodyText"], fontName="Helvetica-Bold", fontSize=8.5, leading=10.5, textColor=colors.white),
        "cell": ParagraphStyle("cell", parent=ss["BodyText"], fontSize=8.1, leading=10.6, textColor=colors.HexColor("#243B36")),
    }
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=2.0 * cm, title="Documentacao de Implementacao - Aquifero Vivo", author="Projeto Aquifero Vivo")
    story = []
    story += [Spacer(1, 2.2 * cm), p("AQUIFERO VIVO", styles["title"]), p("Documentacao de implementacao e pendencias do sistema", styles["subtitle"]), Spacer(1, 1.0 * cm)]
    cover = Table([[p("OBJETIVO", styles["tablehead"]), p("CONCLUSAO", styles["tablehead"])], [p("Consolidar o que esta efetivamente entregue no MVP e separar o que permanece como evolucao.", styles["body"]), p("A base funcional esta pronta para desenvolvimento e demonstracao com dados sinteticos. Recursos de decisao operacional ainda nao foram implementados.", styles["body"])]], colWidths=[8.1 * cm, 8.1 * cm])
    cover.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0B5D50")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("BACKGROUND", (0,1), (-1,-1), colors.HexColor("#EAF5F0")), ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#B7D6CC")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("PADDING", (0,0), (-1,-1), 10)]))
    story += [cover, Spacer(1, .65 * cm), p("Base de analise", styles["h2"]), p("Codigo-fonte do repositorio, documentacao tecnica existente, configuracoes Docker, migrations, testes e interfaces revisados em 20/09/2026. Este documento descreve o estado do codigo; nao transforma dados sinteticos em evidencias reais.", styles["body"]), PageBreak()]

    story += [p("1. Resumo executivo", styles["h1"]), p("O sistema e um monorepo para monitoramento territorial de pocos e setores de abastecimento. A entrega atual funciona como MVP de consulta e demonstracao: armazena dados espaciais no PostgreSQL/PostGIS, expoe API REST versionada, gera dados sinteticos reproduziveis e os apresenta em um mapa web interativo.", styles["body"]), p("O nucleo analitico previsto pelo produto - integracao com SIAGAS, dados reais, modelos de machine learning, motor de risco, alertas operacionais e fluxos de acao - ainda nao foi entregue. Embora existam tabelas para avaliacoes de risco, fatores e alertas, elas sao somente contratos de persistencia sem calculo, endpoint ou interface de uso.", styles["body"]), p("Estado por capacidade", styles["h2"])]
    story.append(status_table([
        ("Infraestrutura local", "Implementado", "Docker Compose com PostgreSQL 17/PostGIS 3.5, backend e frontend; portas expostas somente em loopback."),
        ("Modelo espacial e migracoes", "Implementado", "Alembic 0001-0004, geometrias SRID 4326, indices GiST, UUIDs e auditoria temporal."),
        ("API de leitura", "Implementado", "Health, colecoes paginadas de pocos/setores e consulta unificada de tres tipos de medicao."),
        ("Mapa de pocos", "Implementado", "React, Leaflet, filtros por municipio/setor/status, selecao e popup de detalhes."),
        ("Dados sinteticos", "Implementado", "Geracao, validacao, exportacao CSV, manifesto SHA-256, seed idempotente e proveniencia explicita."),
        ("Dados reais / SIAGAS", "Nao implementado", "Nao ha conector, ETL, politica de atualizacao ou ingestao de fontes externas."),
        ("Risco, ML e alertas", "Nao implementado", "Entidades existem no banco; nao ha algoritmo, servico, endpoints nem telas."),
        ("Qualidade de producao", "Parcial", "Testes de backend existem; faltam lint/formatter, testes de frontend, CI/CD, autenticacao e observabilidade."),
    ], styles))

    story += [p("2. Componentes implementados", styles["h1"]), p("Arquitetura e execucao", styles["h2"]), bullet("<b>Backend:</b> FastAPI 1.0.0 com CORS configuravel, Pydantic Settings, SQLAlchemy 2, GeoAlchemy2 e Uvicorn." , styles), bullet("<b>Persistencia:</b> PostgreSQL com PostGIS; o startup executa <i>alembic upgrade head</i> e nao cria tabelas diretamente pela aplicacao.", styles), bullet("<b>Frontend:</b> React 19, TypeScript, Vite, TanStack Query e React Leaflet. Recharts esta instalado, mas nao ha grafico entregue.", styles), bullet("<b>Ambiente:</b> Compose aguarda a saude do banco; backend e frontend possuem recarga para desenvolvimento local.", styles), p("Modelo de dominio", styles["h2"]), p("Foram implementadas nove entidades principais: Well, ServiceSector, WellSector, GroundwaterMeasurement, OperationalMeasurement, RainfallMeasurement, RiskAssessment, RiskFactor e Alert. As ultimas tres suportam uma evolucao futura, mas nao sao preenchidas por nenhuma regra atual.", styles["body"]), p("As relacoes cobrem series por poco, chuva por setor, vinculo temporal poco-setor, avaliacao de risco e alertas. Ha restricoes para valores negativos, intervalos de vigencia, classificacao de proveniencia e niveis de risco/severidade validos. As geometrias usam WGS 84 e GeoJSON com longitude antes de latitude.", styles["body"])]

    story += [p("3. API e experiencia web", styles["h1"]), p("API REST entregue", styles["h2"])]
    story.append(status_table([
        ("GET /health", "Implementado", "Retorna status do processo da API. Nao consulta o banco; o Compose verifica o banco separadamente."),
        ("GET /api/v1/wells", "Implementado", "Paginacao e filtros q, municipality, sector_id, state e is_active; detalhe por UUID."),
        ("GET /api/v1/sectors", "Implementado", "Paginacao e busca q; detalhe por UUID com limite territorial GeoJSON."),
        ("GET /api/v1/measurements", "Implementado", "Une medicoes groundwater, operational e rainfall; filtra por tipo, periodo, poco/setor, classificacao e fonte."),
        ("Operacoes de escrita", "Nao implementado", "Nao ha endpoints para cadastrar, editar, apagar, reconhecer alerta ou acionar processos."),
        ("Autenticacao / autorizacao", "Nao implementado", "Nao ha usuarios, papeis, tokens, controle de acesso ou trilha de auditoria de acoes."),
    ], styles))
    story += [p("Interface web entregue", styles["h2"]), p("A tela existente e o mapa de pocos. Ela carrega todas as paginas da API, mostra marcadores por situacao operacional, desenha o setor selecionado, ajusta o enquadramento do mapa e oferece filtros por municipio, setor e status. Inclui estados de carregamento, vazio e erro com nova tentativa. Quando os dados sao sinteticos, o popup e o rodape exibem aviso de uso.", styles["body"]), p("Itens de navegacao como Visao geral, Pocos, Setores, Alertas e Configuracoes ainda sao apenas ancoras visuais: nao ha paginas funcionais correspondentes. O contador de alertas e fixo em zero.", styles["body"])]

    story += [p("4. Dados sinteticos e seguranca de proveniencia", styles["h1"]), p("O simulador entrega cenarios NORMAL, DROUGHT e SEVERE_STRESS. Ele modela sazonalidade de chuva, memoria de recarga, demanda, alocacao por capacidade, utilizacao, estresse acumulado, rebaixamento, falha e um indicador demonstrativo de pressao. Uma seed local torna as execucoes reproduziveis.", styles["body"]), p("A configuracao padrao atual produz 80 pocos, 20 setores e 730 dias: 14.600 linhas setor-dia e 146.000 linhas poco-dia no exportador. O seed no banco gera medicoes subterraneas, operacionais e pluviometricas e usa upsert com UUIDs estaveis. A operacao possui lock transacional, rollback em colisao de outra origem e reset restrito ao proprio simulador.", styles["body"]), p("Protecoes entregues", styles["h2"]), bullet("Cada registro sintetico e marcado como <b>SIMULATED</b>, <b>is_synthetic=true</b> e source <b>SIMULATED:AQUIFERO_VIVO</b>.", styles), bullet("Cadastros legados sem fonte conhecida sao preservados como <b>UNKNOWN</b>; o sistema evita rotula-los implicitamente como dados reais.", styles), bullet("CSVs opcionais possuem manifesto, contagens, configuracao, versao e checksums SHA-256.", styles), bullet("O score de risco do gerador nao e persistido como RiskAssessment e nao deve ser interpretado como avaliacao operacional ou cientifica.", styles)]

    story += [p("5. Validacao e estado de qualidade", styles["h1"]), p("A documentacao existente registra uma validacao integrada em 20/09/2026: 49 testes de backend aprovados com PostgreSQL/PostGIS, migrations ate 0004, geracao de cenarios, idempotencia, protecao de origem, filtros de API e geometrias. O build do frontend (TypeScript + Vite) tambem foi aprovado. Esta evidencia depende do registro no repositorio; este relatorio nao executou novamente Docker, banco ou navegador.", styles["body"]), p("Cobertura observada", styles["h2"])]
    story.append(status_table([
        ("Testes backend", "Implementado", "Pytest cobre saude, CORS, schemas, simulacao, banco/PostGIS e API."),
        ("Build frontend", "Implementado", "Script executa tsc --noEmit e vite build."),
        ("Testes frontend", "Nao implementado", "Nao existe framework, suite ou script de testes de componentes/e2e."),
        ("Lint / formatter", "Nao implementado", "Nao ha configuracao de lint/formatador para backend ou frontend."),
        ("CI/CD", "Nao implementado", "Nao foram encontrados pipelines de integracao, entrega ou verificacoes automatizadas remotas."),
        ("Observabilidade", "Nao implementado", "Nao ha logs estruturados, metricas, tracing, alertas de infraestrutura ou monitoramento de dados."),
    ], styles))

    story += [p("6. Pendencias priorizadas", styles["h1"]), p("Prioridade 1 - tornar o MVP seguro e operavel", styles["h2"]), bullet("Implementar autenticacao, autorizacao por perfil, gestao de segredos, rate limiting e auditoria de acoes administrativas.", styles), bullet("Criar CI com testes, build, lint, verificacao de migrations e analise de dependencias; adicionar testes unitarios e e2e do frontend.", styles), bullet("Preparar producao: configuracao por ambiente, imagens imutaveis, proxy/TLS, backups e restauracao PostGIS, logs estruturados, metricas e monitoramento.", styles), p("Prioridade 2 - dados reais e governanca", styles["h2"]), bullet("Construir adaptador SIAGAS/ fontes publicas: extracao, mapeamento de campos, normalizacao de unidades/coordenadas, identificadores externos, deduplicacao e rotina de atualizacao.", styles), bullet("Definir catalogo de fontes, qualidade, licencas, responsaveis, retencao, revisao humana e politicas de correcao. Manter a proveniencia em todo o trajeto.", styles), bullet("Criar fluxos de ingestao e curadoria para dados operacionais reais, com validacao de faixas, consistencia temporal e tratamento de falhas.", styles), p("Prioridade 3 - inteligencia e produto", styles["h2"]), bullet("Definir e validar metodologia de risco com especialistas; implementar calculo versionado, fatores explicaveis, persistencia de avaliacoes e criterios de validade.", styles), bullet("Desenvolver ML somente apos dados reais qualificados, com baseline, avaliacao, monitoramento de drift, reprodutibilidade e aprovacao de uso.", styles), bullet("Expor avaliacoes, alertas e fluxos de reconhecimento/resolucao na API e no frontend; implementar paineis, series temporais, detalhes de poco/setor e exportacoes.", styles), bullet("Substituir os itens de navegacao decorativos por modulos funcionais e adicionar acessibilidade, responsividade testada e suporte a falhas de rede.", styles)]

    story += [p("7. Decisao de prontidao", styles["h1"]), p("O sistema esta pronto como base tecnica de desenvolvimento e demonstracao controlada com dados sinteticos. Nao esta pronto para suportar decisao operacional, alerta real, previsao, classificacao de risco real ou integracao de producao. A liberacao para qualquer uso com dados reais deve ocorrer somente apos as pendencias de seguranca, governanca, integracao, validacao de metodo e operacao assistida serem tratadas.", styles["body"]), Spacer(1, .35 * cm), p("Observacao final: todos os dados sinteticos sao explicitamente demonstrativos. Eles nao representam pocos, setores, medicoes ou situacoes reais.", styles["small"])]
    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
    print(OUT)


if __name__ == "__main__":
    main()
