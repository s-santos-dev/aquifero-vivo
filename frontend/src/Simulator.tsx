import ScenarioControls from './ScenarioControls'
import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getAllPages, getJson, postJson } from './api'

export type Parameters = { rainfall_change_pct: number; demand_change_pct: number; pumping_change_pct: number }
type Preset = Parameters & { label: string }
export type Config = { version: string; min_change_pct: number; max_change_pct: number; presets: Record<string, Preset> }
export type Well = { id: string; code: string; name: string; municipality: string | null; source: string | null; is_synthetic: boolean }
type Input = { indicator: string; value: number | null; unit: string | null }
export type Risk = { score: number | null; status: string; classification: string | null; coverage: number; factors: { group: string; name: string; subscore: number | null; indicators: Input[]; explanation: string }[] }
export type Result = { horizon: number; label: string; applied_parameters: Parameters; risk: Risk; delta_points: number | null; delta_pct: number | null; factors: { group: string; name: string; delta_points: number | null; contribution_delta: number | null; explanation: string }[]; warnings: string[] }
export type Simulation = { well_code: string; reference_date: string | null; source: string | null; data_classification: string; simulation_version: string; baseline: Risk; results: Result[]; assumptions: string[]; warnings: string[] }
const zero: Parameters = { rainfall_change_pct: 0, demand_change_pct: 0, pumping_change_pct: 0 }
export const labels: Record<keyof Parameters, string> = { rainfall_change_pct: 'Precipitação', demand_change_pct: 'Demanda', pumping_change_pct: 'Bombeamento' }
export const classes: Record<string, string> = { NORMAL: 'Normal', ATTENTION: 'Atenção', HIGH: 'Alto', CRITICAL: 'Crítico' }
export const fmt = (n: number | null, suffix = '') => n == null ? 'Dados insuficientes' : !Number.isFinite(n) ? 'Preencha um valor' : `${n.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}${suffix}`
export const signed = (n: number | null) => n == null ? '—' : `${n > 0 ? '+' : ''}${fmt(n)} pontos`
export const notice = 'Os resultados são simulações exploratórias produzidas a partir de indicadores e parâmetros experimentais. Não constituem previsão hidrogeológica validada nem recomendação operacional automática.'

export default function Simulator() {
  const [filter, setFilter] = useState('')
  const [wellId, setWellId] = useState('')
  const [date, setDate] = useState('')
  const wells = useQuery({ queryKey: ['wells', 'catalog'], queryFn: ({ signal }) => getAllPages<Well>('/api/v1/wells', signal) })
  const config = useQuery({ queryKey: ['scenario-config'], queryFn: ({ signal }) => getJson<Config>('/api/v1/scenarios/config', signal) })
  const well = wells.data?.find(w => w.id === wellId)
  return <section className="page"><div className="page-heading"><p>Sensibilidade experimental</p><h2>Simulador de Cenários</h2></div><p className="scenario-notice">{notice}</p>
    {(wells.isPending || config.isPending) && <p role="status">Carregando poços e parâmetros…</p>}
    {(wells.isError || config.isError) && <p role="alert">Não foi possível carregar a API. <button onClick={() => { void wells.refetch(); void config.refetch() }}>Tentar novamente</button></p>}
    <div className="filters"><label>Buscar poço<input aria-label="Buscar poço" placeholder="Código ou nome" value={filter} onChange={e => setFilter(e.target.value)} /></label><label>Poço<select aria-label="Poço" value={wellId} onChange={e => { setWellId(e.target.value); setDate('') }}><option value="">Selecione um poço</option>{wells.data?.filter(w => w.id === wellId || `${w.code} ${w.name}`.toLowerCase().includes(filter.toLowerCase())).map(w => <option key={w.id} value={w.id}>{w.code} · {w.name}</option>)}</select></label><label>Data histórica (UTC)<input aria-label="Data histórica" type="date" value={date} onChange={e => setDate(e.target.value)} /></label></div>
    {wells.data?.length === 0 && <p>Nenhum poço cadastrado.</p>}
    {well && <p>{well.code} · {well.municipality || 'Município não informado'} · {well.is_synthetic ? 'SIMULADO — não representa poço real' : well.source || 'Origem não informada'}</p>}
    {well && config.data && <ScenarioPanel key={`${wellId}:${date}`} wellId={wellId} referenceDate={date} config={config.data} />}
  </section>
}

function ScenarioPanel({ wellId, referenceDate, config }: { wellId: string; referenceDate: string; config: Config }) {
  const [parameters, setParameters] = useState<Parameters>({ ...zero })
  const [dirty, setDirty] = useState(false)
  const request = (p: Parameters, effectiveDate = referenceDate, signal?: AbortSignal) => postJson<Simulation>('/api/v1/scenarios/simulate', { well_id: wellId, ...(effectiveDate ? { reference_date: effectiveDate } : {}), rainfall_change_pct: p.rainfall_change_pct, demand_change_pct: p.demand_change_pct, pumping_change_pct: p.pumping_change_pct, horizons: [30, 60, 90] }, signal)
  const baseline = useQuery({ queryKey: ['scenario-baseline', wellId, referenceDate], queryFn: ({ signal }) => request(zero, referenceDate, signal), retry: 1 })
  const simulation = useMutation({ mutationFn: async (p: Parameters) => {
    const effectiveDate = baseline.data?.reference_date || referenceDate
    const responses = await Promise.all([request(p, effectiveDate), request(config.presets.favorable, effectiveDate), request(config.presets.severe, effectiveDate)])
    return { selected: responses[0], favorable: responses[1], adverse: responses[2] }
  }, onSuccess: () => setDirty(false) })
  const result = simulation.data?.selected
  const shown = result || baseline.data
  const chart = shown?.results.map(r => ({ horizon: `${r.horizon} dias`, baseline: shown.baseline.score, selected: result ? r.risk.score : null, favorable: simulation.data?.favorable.results.find(f => f.horizon === r.horizon)?.risk.score, adverse: simulation.data?.adverse.results.find(f => f.horizon === r.horizon)?.risk.score })) || []
  const update = (p: Parameters) => { setParameters(p); setDirty(true) }
  const valid = Object.values(parameters).every(v => Number.isFinite(v) && v >= config.min_change_pct && v <= config.max_change_pct)
  return <>
    {baseline.isPending && <p role="status">Carregando avaliação de referência…</p>}
    {baseline.isError && <p role="alert">Não foi possível carregar a referência. <button onClick={() => void baseline.refetch()}>Tentar novamente</button></p>}
    {baseline.data && <section className="card"><h3>Condição de referência</h3><p>Referência efetiva: {baseline.data.reference_date || 'Sem medições'} · {baseline.data.data_classification} · {baseline.data.source || 'Origem desconhecida'}</p><p><strong>{fmt(baseline.data.baseline.score, ' / 100')}</strong> · {classes[baseline.data.baseline.classification || ''] || 'Dados insuficientes'} · Cobertura: {fmt(baseline.data.baseline.coverage * 100, '%')}</p><details><summary>Indicadores e fatores da referência</summary>{baseline.data.baseline.factors.map(f => <div key={f.group}><h4>{f.name} · {fmt(f.subscore)}</h4>{f.indicators.map(i => <p key={i.indicator}>{i.indicator}: {fmt(i.value, ` ${i.unit || ''}`)}</p>)}<p>{f.explanation}</p></div>)}</details></section>}
    <section className="card"><h3>Hipóteses ao final de 90 dias</h3><p>Configurações demonstrativas ajustáveis. Progressão parcial em 30 e 60 dias.</p><div className="scenario-actions">{Object.entries(config.presets).map(([key, preset]) => <button key={key} disabled={simulation.isPending} onClick={() => update({ rainfall_change_pct: preset.rainfall_change_pct, demand_change_pct: preset.demand_change_pct, pumping_change_pct: preset.pumping_change_pct })}>{preset.label}</button>)}</div>
      <ScenarioControls parameters={parameters} config={config} disabled={simulation.isPending} onChange={update} />
      <div className="scenario-actions"><button disabled={!baseline.data || !valid || simulation.isPending} onClick={() => simulation.mutate({ ...parameters })}>{simulation.isPending ? 'Simulando…' : 'Simular'}</button><button disabled={simulation.isPending} onClick={() => { setParameters({ ...zero }); simulation.reset(); setDirty(false) }}>Restaurar parâmetros</button></div>
      {!valid && <p role="alert">Preencha os três percentuais entre {config.min_change_pct}% e {config.max_change_pct}%.</p>}{simulation.isError && <p role="alert">{simulation.error.message}</p>}{simulation.isPending && <p role="status">Calculando cenários na API…</p>}{dirty && result && <p>Parâmetros alterados. Clique em Simular para atualizar os resultados abaixo.</p>}
    </section>
    {shown && <section className="card"><h3>Comparação dos índices experimentais</h3>{shown.baseline.score == null && <p role="status">Dados insuficientes: índice e classificação indisponíveis. Escolha outra data ou verifique a cobertura.</p>}{result ? <><div className="scenario-chart"><ResponsiveContainer width="100%" height={320}><BarChart data={chart}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="horizon" /><YAxis domain={[0, 100]} /><Tooltip /><Legend /><Bar dataKey="baseline" name="Índice de referência" fill="#64748b" /><Bar dataKey="selected" name="Índices sob hipóteses simuladas" fill="#087f5b" /><Bar dataKey="favorable" name="Condições favoráveis" fill="#38bdf8" /><Bar dataKey="adverse" name="Estresse severo" fill="#ea580c" /></BarChart></ResponsiveContainer></div><div className="data-table"><table><thead><tr><th>Horizonte hipotético</th><th>Referência</th><th>Selecionado / diferença</th><th>Favorável / diferença</th><th>Adverso / diferença</th></tr></thead><tbody>{result.results.map((r, i) => <tr key={r.horizon}><td>{r.label}</td><td>{fmt(result.baseline.score)}</td><td>{fmt(r.risk.score)} / {signed(r.delta_points)}<small>{classes[r.risk.classification || ''] || 'Dados insuficientes'} · Cobertura {fmt(r.risk.coverage * 100, '%')}</small></td><td>{fmt(simulation.data!.favorable.results[i].risk.score)} / {signed(simulation.data!.favorable.results[i].delta_points)}</td><td>{fmt(simulation.data!.adverse.results[i].risk.score)} / {signed(simulation.data!.adverse.results[i].delta_points)}</td></tr>)}</tbody></table></div>{result.results.map(r => <details key={r.horizon}><summary>Fatores e hipóteses — {r.horizon} dias</summary><p>{(Object.keys(labels) as (keyof Parameters)[]).map(k => `${labels[k]} ${fmt(r.applied_parameters[k], '%')}`).join(' · ')}</p>{r.factors.map(f => <p key={f.group}><strong>{f.name}: {signed(f.delta_points)} no subscore; {signed(f.contribution_delta)} no índice.</strong> {f.explanation}</p>)}{r.warnings.map(w => <p key={w}>{w}</p>)}</details>)}</> : <p>Altere as hipóteses e clique em Simular para comparar 30, 60 e 90 dias.</p>}</section>}
    {shown && <section className="card"><h3>Premissas e limitações · {shown.simulation_version}</h3>{shown.assumptions.map(a => <p key={a}>{a}</p>)}{shown.warnings.map(w => <p key={w}>{w}</p>)}</section>}
  </>
}


