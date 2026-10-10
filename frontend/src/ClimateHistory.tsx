import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getJson, type Page } from './api'

type Station = { id: string; official_code: string; name: string; source: string; latitude: number; longitude: number; distance_km: number; period: { start: string; end: string }; coverage: { observed_fraction: number | null }; quality_status: string }
type Day = { date: string; value_mm: string | null; availability: string; observed_hours: number }
type History = Page<Day> & { station: Station }

export default function ClimateHistory({ wellId, publicPeriod }: { wellId: string; publicPeriod?: { start: string; end: string } }) {
  const [stationId, setStationId] = useState('')
  const [range, setRange] = useState<{ start: string; end: string } | null>(null)
  const nearby = useQuery({ queryKey: ['nearby-climate', wellId], queryFn: ({ signal }) => getJson<Page<Station>>(`/api/v1/wells/${wellId}/nearby-climate?radius_km=100&page_size=20`, signal) })
  const stations = nearby.data?.items || []
  const station = stations.find(s => s.id === stationId) || stations.find(s => s.official_code === 'A237') || stations[0]
  const end = range?.end || station?.period.end || ''
  const initial = end ? new Date(`${end}T00:00:00Z`) : null
  if (initial) initial.setUTCDate(initial.getUTCDate()-89)
  const start = range?.start || initial?.toISOString().slice(0,10) || ''
  const valid = Boolean(start && end && start<=end && (Date.parse(end)-Date.parse(start))/86400000<=365)
  const path = `/api/v1/climate/stations/${station?.id}/rainfall?resolution=daily&start=${start}&end=${end}&page_size=100`
  const history = useQuery({ queryKey: ['climate-history',path], enabled: Boolean(station && valid), queryFn: async ({ signal }) => {
    const first = await getJson<History>(path,signal)
    const rows = [...first.items]
    for (let page=2;page<=Math.min(first.pages,4);page++) rows.push(...(await getJson<History>(`${path}&page=${page}`,signal)).items)
    return rows
  } })
  const days = history.data || []
  const overlapStart = publicPeriod ? [publicPeriod.start, start].sort().at(-1)! : ''
  const overlapEnd = publicPeriod ? [publicPeriod.end, end].sort()[0] : ''
  const complete = days.filter(d=>d.availability==='COMPLETE').length
  const chart = days.map(d=>({...d, rain: d.value_mm === null ? null : Number(d.value_mm)}))
  return <section className="history-panel" aria-label="Precipitação próxima — dados públicos">
    <header><h2>Precipitação próxima — dados públicos</h2></header>
    <p>Comparação territorial exploratória. A chuva desta estação não representa automaticamente a precipitação no poço; estes dados não alimentam o risco.</p>
    {nearby.isError ? <p role="alert">Não foi possível consultar estações climáticas próximas.</p> : nearby.isPending ? <p role="status">Consultando fontes climáticas…</p> : !station ? <p>Nenhuma fonte climática importada em até 100 km.</p> : <>
      <label>Estação meteorológica<select aria-label="Estação meteorológica" value={station.id} onChange={e=>{setStationId(e.target.value);setRange(null)}}>{stations.map(s=><option key={s.id} value={s.id}>{s.official_code} · {s.name} · {s.source}</option>)}</select></label>
      <p><b>{station.name} ({station.official_code}) · INMET</b> · {station.distance_km.toLocaleString('pt-BR',{maximumFractionDigits:2})} km do poço · {station.latitude.toFixed(5)}, {station.longitude.toFixed(5)}</p>
      <p>Disponibilidade importada: {station.period.start} a {station.period.end}. Observação de estação automática, mm por hora anterior. Qualidade por leitura não informada.</p>
      {publicPeriod && <p>Interseção das janelas consultadas: {overlapStart <= overlapEnd ? `${overlapStart} a ${overlapEnd}` : 'sem período comum'}. Comparação de datas de calendário; o fuso RIMAS não foi confirmado. Não representa sincronização das observações nem cobertura conjunta.</p>}
      <form key={station.id} className="history-controls" onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);setRange({start:String(f.get('start')),end:String(f.get('end'))})}}>
        <label>Data inicial<input type="date" name="start" aria-label="Data inicial precipitação" defaultValue={start} required /></label>
        <label>Data final<input type="date" name="end" aria-label="Data final precipitação" defaultValue={end} required /></label><button type="submit">Consultar precipitação</button>
      </form>
      {!valid ? <p role="alert">Selecione um período válido de até 366 dias.</p> : history.isError ? <p role="alert">Não foi possível consultar o histórico de precipitação.</p> : history.isPending ? <p role="status">Carregando precipitação…</p> : <>
        <p>{complete} de {days.length} dias completos ({days.length ? (100*complete/days.length).toFixed(1) : '0'}% de cobertura diária) · {start} a {end} · UTC · mm/dia</p>
        <p>Dias incompletos permanecem sem valor. Zero é chuva observada de 0 mm. O dia UTC soma somente 24 intervalos horários independentes; RIMAS tem leituras em horários variados e fuso desconhecido. Painéis separados não estabelecem alinhamento temporal exato nem relação causal.</p>
        {!complete && <p role="status">Dados insuficientes: nenhum dia completo neste período.</p>}
        <div className="history-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart} accessibilityLayer margin={{top:12,right:22,left:10,bottom:12}}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" tickFormatter={d=>String(d).slice(5)} /><YAxis unit=" mm" width={75} /><Tooltip content={({active,payload,label})=>{const d=chart.find(r=>r.date===label);return active && d ? <div className="card"><b>{d.date} · UTC</b><p>{d.value_mm === null ? 'Dados insuficientes' : `${Number(d.value_mm).toLocaleString('pt-BR')} mm`}</p><p>{d.observed_hours}/24 horas · INMET · qualidade não informada</p></div> : active && payload?.length ? <p>{label}</p> : null}} /><Bar name="INMET · precipitação diária (mm)" dataKey="rain" fill="#3182ce" isAnimationActive={false} /></BarChart></ResponsiveContainer></div>
        <details><summary>Dias ausentes ou incompletos ({days.length-complete})</summary>{days.filter(d=>d.availability!=='COMPLETE').map(d=><p key={d.date}>{d.date} · {d.observed_hours}/24 horas disponíveis · sem total diário</p>)}</details>
        <details><summary>Valores diários e cobertura</summary><div className="history-table"><table><caption>Indicador diário derivado de observações INMET · UTC</caption><thead><tr><th>Data</th><th>Precipitação (mm)</th><th>Horas observadas</th></tr></thead><tbody>{days.map(d=><tr key={d.date}><td>{d.date}</td><td>{d.value_mm === null ? 'Ausente / insuficiente' : Number(d.value_mm).toLocaleString('pt-BR')}</td><td>{d.observed_hours}/24</td></tr>)}</tbody></table></div></details>
      </>}
      <p>Distância geodésica PostGIS sobre elipsoide WGS84. Diferenças locais de chuva e frequência limitam a comparação. Sem inferência de recarga ou tempo de resposta do aquífero.</p>
      <a href="https://portal.inmet.gov.br/dadoshistoricos/" target="_blank" rel="noreferrer">Fonte oficial e arquivos anuais INMET</a>
    </>}
  </section>
}
