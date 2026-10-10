import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { getJson, type Page } from './api'
import ClimateHistory from './ClimateHistory'

type Reading = { id: string; measured_at: string; observed_level_m: string; source: string; unit: string; pumping: string | null; source_record_id: string; source_metadata: { original_date: string; original_time: string; extracted_at: string; batch: string; timezone: string; quality_status: string } }
const dateLabel = (n: number) => new Date(n).toLocaleDateString('pt-BR', { timeZone: 'UTC' })

export default function RimasHistory({ wellId }: { wellId: string }) {
  const [range, setRange] = useState<{ start: string; end: string } | null>(null)
  const [page, setPage] = useState(1)
  const path = `/api/v1/measurements?type=groundwater&source=RIMAS&well_id=${wellId}`
  const latest = useQuery({ queryKey: ['rimas-latest', wellId], queryFn: ({ signal }) => getJson<Page<Reading>>(`${path}&page_size=1`, signal) })
  const last = latest.data?.items[0]?.measured_at.slice(0, 10)
  const first = last ? new Date(`${last}T00:00:00Z`) : null
  if (first) first.setUTCDate(first.getUTCDate() - 89)
  const start = range?.start || first?.toISOString().slice(0, 10) || ''
  const end = range?.end || last || ''
  const valid = !!start && !!end && start <= end && (Date.parse(end) - Date.parse(start)) / 86400000 <= 365
  const queryPath = `${path}&measured_from=${start}T00:00:00&measured_to=${end}T23:59:59&page_size=100`
  const series = useQuery({ queryKey: ['rimas-series', queryPath], enabled: valid, queryFn: async ({ signal }) => {
    const result = await getJson<Page<Reading>>(`${queryPath}&page=1`, signal)
    const rows = [...result.items]
    // Bound browser work as well as API responses; no unbounded history download.
    for (let p = 2; p <= Math.min(result.pages, 10); p++) rows.push(...(await getJson<Page<Reading>>(`${queryPath}&page=${p}`, signal)).items)
    return { rows, total: result.total }
  } })
  const rows = series.data?.rows || []
  // UTC here is a plotting coordinate only. Labels use original wall-clock fields.
  const points = rows.map(r => ({ x: Date.parse(`${r.measured_at}Z`), y: Number(r.observed_level_m), reading: r })).sort((a,b) => a.x-b.x)
  return <section className="history-panel" aria-label="Histórico real RIMAS">
    <header><h2>Histórico real RIMAS/SGB</h2></header>
    <p>Observações públicas de nível d’água em metros. Referência e fuso horário não informados. Indicadores e risco: dados insuficientes; série não habilitada para avaliação.</p>
    <form key={`${wellId}:${last}`} className="history-controls" onSubmit={e => { e.preventDefault(); const fields = new FormData(e.currentTarget); setRange({ start: String(fields.get('start')), end: String(fields.get('end')) }); setPage(1) }}><label>Data inicial<input name="start" aria-label="Data inicial RIMAS" type="date" defaultValue={start} required /></label><label>Data final<input name="end" aria-label="Data final RIMAS" type="date" defaultValue={end} required /></label><button type="submit" disabled={!last}>Consultar período</button></form>
    {!valid && last && <p role="alert">Selecione um intervalo de até 366 dias, com início anterior ao fim.</p>}
    {latest.isError || series.isError ? <p role="alert">Não foi possível consultar a série RIMAS.</p> : latest.isPending || (valid && series.isPending) ? <p role="status">Carregando observações reais…</p> : !rows.length ? <p>Nenhuma observação RIMAS neste período.</p> : <>
      <p>{series.data?.total} observações · {start} a {end} · fonte RIMAS/SGB · unidade m</p>
      <p>Cobertura descritiva: {new Set(rows.map(r => r.measured_at.slice(0,10))).size} dias com observações entre os {Math.round((Date.parse(end) - Date.parse(start)) / 86400000) + 1} dias consultados{rows.length < (series.data?.total || 0) ? ' (apenas o subconjunto exibido)' : ''}. Não representa validação operacional ou confiança preditiva.</p><p>Horários originais preservados, inclusive leituras no mesmo dia. Pontos sem interpolação ou consolidação diária. Bombeamento e qualidade devem ser considerados antes de qualquer análise.</p>
      {rows.length < (series.data?.total || 0) && <p role="status">Exibindo as {rows.length} observações mais recentes. Reduza o intervalo para consultar todas.</p>}
      <div className="history-chart"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{ top: 12, right: 22, left: 10, bottom: 12 }} accessibilityLayer><CartesianGrid strokeDasharray="3 3" /><XAxis type="number" dataKey="x" domain={['dataMin', 'dataMax']} tickFormatter={dateLabel} name="Data original" /><YAxis type="number" dataKey="y" domain={['auto', 'auto']} name="Nível observado" unit=" m" width={70} /><Tooltip content={({ active, payload }) => { const r = payload?.[0]?.payload?.reading as Reading | undefined; return active && r ? <div className="card"><b>{r.source_metadata.original_date} {r.source_metadata.original_time}</b><p>{r.observed_level_m} m · RIMAS/SGB</p><p>Fuso não informado · bombeando: {r.pumping === 'S' ? 'sim' : r.pumping === 'N' ? 'não' : 'desconhecido'}</p></div> : null }} /><Scatter name="RIMAS/SGB · nível observado (m)" data={points} fill="#087f5b" isAnimationActive={false} /></ScatterChart></ResponsiveContainer></div>
      <div className="history-table"><table><caption>Leituras originais RIMAS/SGB · fuso não informado</caption><thead><tr><th>Data e hora originais</th><th>Nível (m)</th><th>Bombeando</th><th>Sequência oficial</th><th>Qualidade</th></tr></thead><tbody>{rows.slice((page-1)*20,page*20).map(r => <tr key={r.id}><td>{r.source_metadata.original_date} {r.source_metadata.original_time}</td><td>{Number(r.observed_level_m).toLocaleString('pt-BR')}</td><td>{r.pumping === 'S' ? 'Sim' : r.pumping === 'N' ? 'Não' : 'Desconhecido'}</td><td>{r.source_record_id}</td><td>Não informada</td></tr>)}</tbody></table></div>
      <div className="history-pagination"><button disabled={page<=1} onClick={() => setPage(page-1)}>Anterior</button><span>Página {page} de {Math.ceil(rows.length/20)}</span><button disabled={page>=Math.ceil(rows.length/20)} onClick={() => setPage(page+1)}>Próxima</button></div>
      <p>Extração: {rows[0].source_metadata.extracted_at} · lote {rows[0].source_metadata.batch}</p>
    </>}
    <ClimateHistory wellId={wellId} publicPeriod={valid ? { start, end } : undefined} />
  </section>
}
