type Recommendation = { rule_id: string; justification: string; suggestions: string[]; evidence: { indicator: string; value: number | null; unit: string | null }[] }

export const meanings: Record<string, string> = {
  NORMAL: 'Sem prioridade elevada segundo o índice disponível.',
  ATTENTION: 'Condições que merecem acompanhamento.',
  HIGH: 'Investigação prioritária.',
  CRITICAL: 'Investigação de prioridade crítica.',
  INSUFFICIENT_DATA: 'Dados insuficientes para avaliação.',
}
export const investigationNames: Record<string, string> = {
  STATIC_TREND: 'Conferir medições de nível', RAINFALL_DEFICIT: 'Investigar redução relativa da chuva',
  PUMPING_LOAD: 'Avaliar regime de bombeamento', DEMAND_PRESSURE: 'Investigar demanda crescente',
  RECENT_FAILURES: 'Conferir registros de falhas', DATA_COVERAGE: 'Obter e validar dados adicionais',
}
const related: Record<string, string> = {
  STATIC_TREND: 'Profundidade da água ao longo do tempo', RAINFALL_DEFICIT: 'Chuva recente e anterior',
  PUMPING_LOAD: 'Horas de bombeamento', DEMAND_PRESSURE: 'Variação da demanda',
  RECENT_FAILURES: 'Falhas registradas', DATA_COVERAGE: 'Disponibilidade de informações',
}
const glossary: Record<string, string> = {
  'Nível estático': 'Profundidade da água em repouso, em metros abaixo da referência de medição. No conjunto sintético, um valor maior significa água mais profunda.',
  'Nível dinâmico': 'Profundidade da água durante o bombeamento, medida na mesma referência do nível estático.',
  'Rebaixamento': 'Aumento da profundidade da água em relação a uma referência. A tendência temporal e a diferença durante bombeamento são medidas distintas.',
  Drawdown: 'Diferença entre nível dinâmico e estático, em metros, na mesma data e referência. Não é uma previsão de nível futuro.',
  'Déficit relativo de precipitação': 'Compara a chuva dos 30 dias recentes com os 30 dias anteriores. Não representa uma normal climatológica nem comprova redução de recarga.',
  Demanda: 'Volume diário solicitado, em m³/dia. Sua variação relativa compara médias de períodos consecutivos.',
  'Utilização operacional': 'Carga planejada em relação à capacidade nominal diária simulada, equivalente às horas solicitadas divididas por 24. Não mede capacidade hidráulica comprovada.',
  'Índice multicritério': 'Combinação ponderada de grupos de indicadores, entre 0 e 100, para priorizar investigação. Pesos e limites experimentais; não é probabilidade de colapso.',
  'Cobertura de dados': 'No risco, proporção ponderada dos grupos com dados válidos. Nos indicadores, dias observados e exigidos. Não é confiança preditiva.',
  'Dados sintéticos': 'Registros criados para demonstração. Não representam medições reais ou operação de concessionárias.',
}

export function Glossary() {
  return <details className="decision-glossary"><summary>Entenda os termos usados</summary><div className="glossary-grid">{Object.entries(glossary).map(([term, explanation]) => <details key={term}><summary>{term}</summary><p>{explanation}</p></details>)}</div></details>
}

export function TermHelp({ term }: { term: string }) {
  return <details className="term-help"><summary aria-label={`Explicação: ${term}`}>O que significa?</summary><p>{glossary[term]}</p></details>
}

export function Investigations({ items, technical = false }: { items: Recommendation[]; technical?: boolean }) {
  return <div className="investigations">{!items.length && <p>Nenhuma investigação foi sugerida pelos dados disponíveis. Isso não confirma ausência de risco.</p>}{items.map(item => <article className="demo-recommendation" key={item.rule_id}>
    <h4>{investigationNames[item.rule_id] || item.rule_id}</h4>
    <ul>{item.suggestions.map(s => <li key={s}>{s}</li>)}</ul>
    <details open={technical || undefined}><summary>Por que esta sugestão apareceu?</summary><p>Fator relacionado: {related[item.rule_id] || item.rule_id}.</p><p>{item.justification}</p><p>Regra: {item.rule_id}</p>{item.evidence.map(e => <p key={e.indicator}>{e.indicator}: {e.value == null ? 'Indisponível' : e.value.toLocaleString('pt-BR', { maximumFractionDigits: 6 })} {e.unit}</p>)}</details>
  </article>)}{items.length > 0 && <p>As sugestões orientam a investigação e exigem avaliação humana.</p>}</div>
}
