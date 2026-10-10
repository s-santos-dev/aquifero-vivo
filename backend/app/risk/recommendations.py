"""Evidence-based suggestions for human review; never operating commands."""
from app.schemas.priority import Recommendation


def recommendations(risk):
    result = []
    if risk.status == 'INSUFFICIENT_DATA':
        result.append(Recommendation(rule_id='DATA_COVERAGE', justification='Cobertura mínima ou grupo essencial indisponível.', suggestions=['Revisar registros de medição e atualização dos dados.', 'Verificar integridade, unidades e proveniência.']))
    rules = (
        ('STATIC_TREND', 'static_level_trend_30d', 0, 'Tendência positiva da profundidade estática em 30 dias completos; não comprova persistência futura.', ['Conferir consistência das medições e histórico de nível.', 'Avaliar condições de bombeamento e necessidade de inspeção técnica.']),
        ('RAINFALL_DEFICIT', 'recent_rainfall_deficit_30d', .3, 'Déficit relativo de chuva superior a 0,30 entre janelas adjacentes; não comprova perda de recarga.', ['Intensificar acompanhamento das medições.', 'Verificar disponibilidade cadastrada de fontes alternativas e histórico do sistema.']),
        ('PUMPING_LOAD', 'pumping_hours_avg_30d', 16, 'Média de bombeamento superior a 16 h/dia em janela completa; não implica tendência crescente.', ['Submeter o regime de operação à revisão técnica.', 'Conferir produção e demanda e avaliar inspeção operacional.']),
        ('DEMAND_PRESSURE', 'demand_pressure_30d', .2, 'Aumento relativo da demanda superior a 0,20 entre janelas completas.', ['Conferir registros de produção e demanda.', 'Avaliar tecnicamente a pressão sobre o regime de operação.']),
        ('RECENT_FAILURES', 'failures_30d', 0, 'Há dias com falha operacional em 30 dias completos.', ['Inspecionar registros de manutenção e condições do conjunto motobomba.', 'Avaliar necessidade de manutenção preventiva.']),
    )
    inputs = {item.indicator: item for factor in risk.factors for item in factor.indicators}
    for rule, key, threshold, justification, suggestions in rules:
        item = inputs.get(key)
        if item and item.status == 'AVAILABLE' and item.normalized is not None and item.value > threshold:
            result.append(Recommendation(rule_id=rule, justification=justification, suggestions=suggestions, evidence=[item]))
    return result
