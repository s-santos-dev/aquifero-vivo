VERSION = "sensitivity-v1.0.0"
HORIZONS = (30, 60, 90)
PROGRESSION = {30: 1 / 3, 60: 2 / 3, 90: 1.0}
MIN_CHANGE = -100
MAX_CHANGE = 100
MAX_HOURS = 24
PRESETS = {
    "reference": {"label": "Cenário de Referência", "rainfall_change_pct": 0, "demand_change_pct": 0, "pumping_change_pct": 0},
    "favorable": {"label": "Condições Favoráveis", "rainfall_change_pct": 20, "demand_change_pct": -10, "pumping_change_pct": -15},
    "drought": {"label": "Cenário de Estiagem", "rainfall_change_pct": -30, "demand_change_pct": 15, "pumping_change_pct": 10},
    "severe": {"label": "Cenário de Estresse Severo", "rainfall_change_pct": -60, "demand_change_pct": 30, "pumping_change_pct": 20},
}
WARNINGS = [
    "Os resultados são simulações exploratórias produzidas a partir de indicadores e parâmetros experimentais. Não constituem previsão hidrogeológica validada nem recomendação operacional automática.",
    "Níveis estáticos, drawdown, vazão e falhas permanecem constantes: não há modelo físico ou estatístico calibrado.",
    "Utilização representa tempo solicitado, não capacidade hidráulica. Horas efetivas são limitadas a 24 por dia; utilização solicitada pode exceder 1.",
    "Saturação e dados insuficientes podem impedir alterações do índice. Cobertura não é confiança preditiva.",
]
ASSUMPTIONS = [
    "Multiplicador por horizonte: 1 + (alteração percentual / 100) × progressão configurada (30: 1/3; 60: 2/3; 90: 1).",
    "Chuva recente de 30 dias é multiplicada; janela anterior permanece fixa. Déficit = max(0, 1 − chuva recente / chuva anterior).",
    "Demanda recente é multiplicada; pressão = (1 + pressão original) × multiplicador − 1, com janela anterior fixa.",
    "Horas médias = min(24, horas originais × multiplicador de bombeamento); utilização solicitada é multiplicada sem teto hidráulico.",
    "Volume médio é ajustado pela razão das horas efetivas, mantendo vazão constante; demais janelas e tendências não são extrapoladas.",
    "Os horizontes descrevem sensibilidade de uma janela recente hipotética, não datas de observações futuras.",
]
