import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getAllPages, getJson, type Page } from './api'
import { Indicators } from './Indicators'

type Kind = 'groundwater' | 'operational' | 'rainfall'
type Measurement = {
  id: string; measured_at: string; is_synthetic: boolean; source: string | null
  data_classification: string; operational_failure: boolean | null
} & Record<Metric, string | number | null>
type Metric = 'water_level_m' | 'dynamic_level_m' | 'flow_rate_m3_h' | 'pumped_volume_m3' | 'daily_demand_m3' | 'runtime_hours' | 'utilization' | 'precipitation_mm'
const metrics: Record<Kind, { key: Metric; label: string; unit: string }[]> = {
  groundwater: [{ key: 'water_level_m', label: 'Nível estático', unit: 'm' }, { key: 'dynamic_level_m', label: 'Nível dinâmico', unit: 'm' }],
  operational: [{ key: 'flow_rate_m3_h', label: 'Vazão', unit: 'm³/h' }, { key: 'pumped_volume_m3', label: 'Volume bombeado', unit: 'm³' }, { key: 'daily_demand_m3', label: 'Demanda diária', unit: 'm³/dia' }, { key: 'runtime_hours', label: 'Bombeamento', unit: 'h' }, { key: 'utilization', label: 'Utilização', unit: '%' }],
  rainfall: [{ key: 'precipitation_mm', label: 'Precipitação', unit: 'mm' }],
}
const labels: Record<Kind, string> = { groundwater: 'Níveis subterrâneos', operational: 'Operação', rainfall: 'Precipitação do setor' }
const formatDate = (value: string | number) => new Date(value).toLocaleDateString('pt-BR', { timeZone: 'UTC' })
const numeric = (row: Measurement, key: Metric) => row[key] == null ? null : Number(row[key]) * (key === 'utilization' ? 100 : 1)
const formatValue = (value: number | null) => value == null ? '—' : value.toLocaleString('pt-BR', { maximumFractionDigits: 2 })
type Entity = { id: string; name: string; code: string }

export function MeasurementHistory({ well, sector }: { well: Entity | null; sector: Entity | null }) {
  const [search] = useSearchParams()
  const referenceDate = search.get('reference_date') || ''
  const [kind, setKind] = useState<Kind>(well ? 'groundwater' : 'rainfall')
  const entity = kind === 'rainfall' ? sector : well
  return <section className="history-panel" aria-label="Histórico de medições">
    <header><div><h2>Histórico de medições</h2><p>{entity?.name} · {entity?.code}</p></div></header>
    <div className="history-tabs" role="group" aria-label="Tipo de medição">{(Object.keys(labels) as Kind[]).filter((type) => type === 'rainfall' ? sector : well).map((type) => <button key={type} aria-pressed={kind === type} onClick={() => setKind(type)}>{labels[type]}</button>)}</div>
    {kind === 'rainfall' && <p>A chuva corresponde ao setor selecionado no filtro do mapa.</p>}
    {well && <Indicators wellId={well.id} />}
    {entity && <Series key={`${entity.id}:${kind}:${referenceDate}`} kind={kind} entityId={entity.id} referenceDate={referenceDate} />}
  </section>
}

function Series({ kind, entityId, referenceDate }: { kind: Kind; entityId: string; referenceDate: string }) {
  const [days, setDays] = useState(90)
  const [metric, setMetric] = useState<Metric>(metrics[kind][0].key)
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ type: kind, [kind === 'rainfall' ? 'sector_id' : 'well_id']: entityId })
  if (referenceDate) params.set('measured_to', `${referenceDate}T23:59:59.999999Z`)
  const path = `/api/v1/measurements?${params}`
  const latest = useQuery({ queryKey: ['measurements', path, 'latest'], queryFn: ({ signal }) => getJson<Page<Measurement>>(`${path}&page_size=1`, signal), retry: 1 })
  const end = latest.data?.items[0]?.measured_at
  // Anchor the window to available history, which may end before today's date.
  const start = end ? new Date(end) : null
  if (start) { start.setUTCDate(start.getUTCDate() - days + 1); start.setUTCHours(0, 0, 0, 0) }
  const historyPath = end && start ? `${path}&measured_from=${encodeURIComponent(start.toISOString())}&measured_to=${encodeURIComponent(end)}` : ''
  const history = useQuery({ queryKey: ['measurements', historyPath], queryFn: ({ signal }) => getAllPages<Measurement>(historyPath, signal), enabled: Boolean(historyPath), retry: 1 })
  const rows = history.data ?? []
  const config = metrics[kind].find((item) => item.key === metric)!
  const points = [...rows].reverse().map((row) => ({ date: new Date(row.measured_at).getTime(), value: numeric(row, metric) }))
  const pages = Math.ceil(rows.length / 20)
  const error = latest.isError || history.isError
  const loading = latest.isPending || (Boolean(end) && history.isPending)
  return <>
    <div className="history-controls"><label>Período<select value={days} onChange={(event) => { setDays(Number(event.target.value)); setPage(1) }}>{[30, 90, 365, 730].map((value) => <option key={value} value={value}>Últimos {value} dias disponíveis</option>)}</select></label><label>Indicador<select value={metric} onChange={(event) => setMetric(event.target.value as Metric)}>{metrics[kind].map((item) => <option key={item.key} value={item.key}>{item.label} ({item.unit})</option>)}</select></label></div>
    {error ? <div role="alert"><p>Não foi possível carregar as medições.</p><button onClick={() => { void latest.refetch(); if (end) void history.refetch() }}>Tentar novamente</button></div> : loading ? <p role="status">Carregando histórico…</p> : !rows.length ? <p role="status">Nenhuma medição disponível neste período.</p> : <>
      <p>{rows.length.toLocaleString('pt-BR')} medições · {formatDate(start!.toISOString())} a {formatDate(end!)} (UTC)</p>
      {rows.some((row) => row.is_synthetic) && <p className="history-notice">Dados simulados — não representam medições reais e não devem orientar decisões operacionais reais.</p>}
      <h3>{config.label} ({config.unit})</h3>
      {points.some((point) => point.value != null) ? <div className="history-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={points} margin={{ top: 12, right: 22, left: 10, bottom: 12 }} accessibilityLayer><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" type="number" domain={['dataMin', 'dataMax']} tickFormatter={formatDate} /><YAxis width={65} tickFormatter={(value: number) => formatValue(value)} /><Tooltip labelFormatter={(value) => formatDate(Number(value))} formatter={(value) => [`${formatValue(Number(value))} ${config.unit}`, config.label]} /><Line type="linear" dataKey="value" name={config.label} stroke="#087f5b" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></div> : <p>Indicador sem valores neste período.</p>}
      <div className="history-table"><table><caption>Medições em ordem da mais recente para a mais antiga</caption><thead><tr><th>Data (UTC)</th>{metrics[kind].map((item) => <th key={item.key}>{item.label} ({item.unit})</th>)}{kind === 'operational' && <th>Falha registrada</th>}<th>Origem</th></tr></thead><tbody>{rows.slice((page - 1) * 20, page * 20).map((row) => <tr key={row.id}><td>{formatDate(row.measured_at)} {new Date(row.measured_at).toLocaleTimeString('pt-BR', { timeZone: 'UTC' })}</td>{metrics[kind].map((item) => <td key={item.key}>{formatValue(numeric(row, item.key))}</td>)}{kind === 'operational' && <td>{row.operational_failure == null ? '—' : row.operational_failure ? 'Sim' : 'Não'}</td>}<td>{row.is_synthetic ? 'SIMULADO' : row.data_classification} · {row.source || 'Fonte não informada'}</td></tr>)}</tbody></table></div>
      <div className="history-pagination"><button disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span aria-live="polite">Página {page} de {pages}</span><button disabled={page >= pages} onClick={() => setPage(page + 1)}>Próxima</button></div>
    </>}
  </>
}
