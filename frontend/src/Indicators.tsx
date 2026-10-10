import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getJson } from './api'
import { Risk } from './Risk'
import { TermHelp } from './DecisionSupport'

type Value = { value: number | null; status: 'AVAILABLE' | 'INSUFFICIENT_DATA'; unit: string; observed_days: number; required_days: number }
export type IndicatorResponse = { reference_date: string; data_classification: string; source: string | null; sector_id: string | null; groundwater: Record<string, Value>; rainfall: Record<string, Value>; operations: Record<string, Value> }
const selected = [
  { group: 'rainfall', key: 'rainfall_30d', label: 'Chuva acumulada · 30 dias' },
  { group: 'rainfall', key: 'rainfall_90d', label: 'Chuva acumulada · 90 dias' },
  { group: 'rainfall', key: 'recent_rainfall_deficit_30d', label: 'Déficit recente de chuva · 30 dias' },
  { group: 'groundwater', key: 'current_static_level', label: 'Nível estático' },
  { group: 'groundwater', key: 'static_level_trend_30d', label: 'Tendência do nível · 30 dias' },
  { group: 'groundwater', key: 'current_drawdown', label: 'Diferença dinâmico − estático' },
  { group: 'operations', key: 'demand_avg_30d', label: 'Demanda média · 30 dias' },
  { group: 'operations', key: 'demand_pressure_30d', label: 'Variação relativa da demanda · 30 dias' },
  { group: 'operations', key: 'pumping_hours_avg_30d', label: 'Bombeamento médio · 30 dias' },
] as const

export function Indicators({ wellId, referenceDateOverride }: { wellId: string; referenceDateOverride?: string }) {
  const [search, setSearch] = useSearchParams()
  const referenceDate = referenceDateOverride ?? (search.get('reference_date') || '')
  const setReferenceDate = (value: string) => { const next = new URLSearchParams(search); value ? next.set('reference_date', value) : next.delete('reference_date'); setSearch(next) }
  const path = `/api/v1/wells/${wellId}/indicators${referenceDate ? `?reference_date=${referenceDate}` : ''}`
  const query = useQuery({ queryKey: ['indicators', wellId, referenceDate], queryFn: ({ signal }) => getJson<IndicatorResponse>(path, signal), retry: 1 })
  return <><section className="indicators" aria-label="Indicadores do poço">
    <div className="indicators-head"><div><h2>Indicadores</h2><p>Calculados a partir das medições armazenadas. Não são classificação de risco.</p></div><label>Data de referência (UTC)<input type="date" value={referenceDate} onChange={(event) => setReferenceDate(event.target.value)} /></label></div>
    {query.isPending ? <p role="status">Calculando indicadores…</p> : query.isError ? <div role="alert"><p>Não foi possível consultar os indicadores.</p><button onClick={() => void query.refetch()}>Tentar novamente</button></div> : <>
      <p>Referência: {query.data.reference_date} · Origem: {query.data.data_classification}{query.data.source ? ` · ${query.data.source}` : ''}</p>
      <IndicatorValues data={query.data} />
      {query.data.sector_id == null && <p>Sem vínculo setorial nessa data: indicadores de chuva indisponíveis.</p>}
      {query.data.data_classification === 'SIMULATED' && <p>Indicadores demonstrativos baseados em dados sintéticos; não usar para decisões operacionais reais.</p>}
    </>}
  </section><Risk wellId={wellId} referenceDate={referenceDate || query.data?.reference_date || ''} /></>
}

export function IndicatorValues({ data }: { data: IndicatorResponse }) {
  return <><div className="indicator-grid">{selected.map(({ group, key, label }) => {
        const value = data[group][key]
        const term = key.includes('deficit') ? 'Déficit relativo de precipitação' : key.includes('drawdown') ? 'Drawdown' : key.includes('demand') ? 'Demanda' : key === 'current_static_level' ? 'Nível estático' : key.includes('trend') ? 'Rebaixamento' : null
        return <div className="indicator-card" key={key}><small>{label}</small>{term && <TermHelp term={term} />}<strong>{value?.status === 'AVAILABLE' && value.value != null ? `${value.value.toLocaleString('pt-BR', { maximumFractionDigits: 6 })} ${value.unit}` : 'Dados insuficientes'}</strong>{value?.status === 'INSUFFICIENT_DATA' && <span>{value.observed_days} de {value.required_days} dias com dados</span>}</div>
      })}</div><details><summary>Todos os indicadores, unidades e cobertura</summary><div className="data-table"><table><thead><tr><th>Grupo / indicador</th><th>Valor original</th><th>Unidade</th><th>Dias válidos / exigidos</th></tr></thead><tbody>{(['groundwater', 'rainfall', 'operations'] as const).flatMap(group => Object.entries(data[group]).map(([key, v]) => <tr key={`${group}:${key}`}><td>{group} / {key}</td><td>{v.status === 'AVAILABLE' && v.value != null ? v.value.toLocaleString('pt-BR', { maximumFractionDigits: 6 }) : 'Dados insuficientes'}</td><td>{v.unit}</td><td>{v.observed_days} / {v.required_days}</td></tr>))}</tbody></table></div></details></>
}
