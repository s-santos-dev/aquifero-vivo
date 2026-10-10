import { useQuery } from '@tanstack/react-query'
import { RecommendationList, type Recommendation } from './Priorities'
import { getJson } from './api'

type Factor = { group: string; name: string; status: string; subscore: number | null; weight: number; effective_weight: number | null; contribution: number | null; explanation: string }
export type RiskResponse = { score: number | null; status: string; classification: 'NORMAL' | 'ATTENTION' | 'HIGH' | 'CRITICAL' | null; reference_date: string | null; coverage: number; minimum_coverage: number; model_version: string; data_classification: string; source: string | null; factors: Factor[]; unavailable_groups: string[] }
const labels = { NORMAL: 'Normal', ATTENTION: 'Atenção', HIGH: 'Alta prioridade', CRITICAL: 'Prioridade crítica' }
const fmt = (value: number | null) => value == null ? '—' : value.toLocaleString('pt-BR', { maximumFractionDigits: 2 })

export function Risk({ wellId, referenceDate }: { wellId: string; referenceDate: string }) {
  const query = useQuery({ queryKey: ['risk-recommendations', wellId, referenceDate], queryFn: ({ signal }) => getJson<{ risk: RiskResponse; recommendations: Recommendation[] }>(`/api/v1/wells/${wellId}/recommendations${referenceDate ? `?reference_date=${referenceDate}` : ''}`, signal), select: response => ({ ...response.risk, recommendations: response.recommendations }), retry: 1 })
  return <section className="indicators" aria-label="Análise de Risco">
    <h2>Análise e Recomendações</h2>
    <p>Índice experimental de priorização preventiva · 0–100</p>
    {query.isPending ? <p role="status">Calculando risco…</p> : query.isError ? <div role="alert"><p>Não foi possível consultar o risco.</p><button onClick={() => void query.refetch()}>Tentar novamente</button></div> : <>
      <div className="indicator-grid">
        <div className="indicator-card"><small>Índice experimental</small><strong>{query.data.score == null ? 'Dados insuficientes' : `${fmt(query.data.score)} / 100`}</strong></div>
        <div className="indicator-card"><small>Classificação</small><strong>{query.data.classification ? labels[query.data.classification] : 'Dados insuficientes'}</strong></div>
        <div className="indicator-card"><small>Cobertura de dados</small><strong>{fmt(query.data.coverage * 100)}%</strong></div>
      </div>
      <p>Referência (UTC): {query.data.reference_date ?? 'Sem medições'} · {query.data.model_version} · Origem: {query.data.data_classification}{query.data.source ? ` · ${query.data.source}` : ''}</p>
      {query.data.status === 'INSUFFICIENT_DATA' && <p>É necessária cobertura ponderada de pelo menos {fmt(query.data.minimum_coverage * 100)}% e dados válidos de estresse subterrâneo.</p>}
      <h3>Subscores e fatores contribuintes</h3>
      <div className="indicator-grid">{query.data.factors.map((factor) => <div className="indicator-card" key={factor.group}>
        <small>{factor.name}</small><strong>{factor.subscore == null ? 'Dados insuficientes' : `${fmt(factor.subscore)} / 100`}</strong>
        <span>Peso inicial: {fmt(factor.weight * 100)}%{factor.effective_weight != null ? ` · Efetivo: ${fmt(factor.effective_weight * 100)}%` : ''}</span>
        <span>Contribuição: {factor.contribution == null ? 'Não calculada' : `${fmt(factor.contribution)} pontos`}</span>
        <p>{factor.explanation}</p>
      </div>)}</div>
      {query.data.data_classification === 'SIMULATED' && <p>Esta avaliação utiliza dados simulados.</p>}
    </>}
    {query.data && <RecommendationList items={query.data.recommendations} />}
    <details><summary>Metodologia da avaliação</summary><p>O motor normaliza indicadores em subscores entre 0 e 100 e combina os grupos pelos pesos exibidos. Dados ausentes não são tratados como zero. Exige cobertura ponderada mínima de 80% e grupo subterrâneo válido; grupos ausentes são informados, e pesos efetivos refletem os grupos disponíveis.</p><p>Déficit de chuva compara janelas adjacentes de 30 dias. Tendências descrevem o histórico; níveis mais profundos usam valores maiores na referência sintética. O índice não demonstra causalidade.</p><p>Classificação v1: Normal abaixo de 40; Atenção de 40 até menos de 60; Alta de 60 até menos de 80; Crítica a partir de 80. Versão efetiva: {query.data?.model_version || 'indisponível'}.</p></details><p>Os pesos e limites são experimentais e não estão validados. O índice não é probabilidade de colapso nem previsão de esgotamento; não fundamenta decisões operacionais reais sem calibração e validação.</p>
  </section>
}
