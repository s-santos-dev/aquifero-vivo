import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { getAllPages, getJson, type Page } from './api'

export const priorityLabels = { NORMAL: 'Normal', ATTENTION: 'Atenção', HIGH: 'Prioridade alta', CRITICAL: 'Prioridade crítica', INSUFFICIENT_DATA: 'Dados insuficientes' }
export const priorityColors = { NORMAL: '#168354', ATTENTION: '#d5a600', HIGH: '#ea7c20', CRITICAL: '#d63038', INSUFFICIENT_DATA: '#78838c' }
export type Recommendation = { rule_id: string; justification: string; suggestions: string[]; evidence: { indicator: string; value: number; unit: string }[] }
export type Priority = { well_id: string; well_code: string; municipality: string | null; sector_id: string | null; sector_code: string | null; sector_name: string | null; score: number | null; classification: keyof typeof priorityLabels | null; status: string; coverage: number; reference_date: string | null; data_classification: string; source: string | null; model_version: string; factors: { name: string; contribution: number | null; explanation: string }[]; recommendations: Recommendation[] }
type Ranking = Page<Priority> & { reference_date: string | null; distribution: Record<string, number>; evaluated: number; insufficient: number; high_priority: number }
type Alert = { id: string; kind: string; message: string; evaluation: Priority }
export const priorityName = (risk: Priority) => priorityLabels[risk.classification || 'INSUFFICIENT_DATA']

export function RecommendationList({ items }: { items: Recommendation[] }) {
  return <><h3>Recomendações de investigação</h3>{items.length === 0 && <p>Nenhuma regra de investigação acionada pelos indicadores disponíveis.</p>}{items.map(item => <article className="indicator-card" key={item.rule_id}><b>{item.rule_id}</b><p>{item.justification}</p>{item.evidence.map(e => <small key={e.indicator}>{e.indicator}: {e.value.toLocaleString('pt-BR')} {e.unit}</small>)}<ul>{item.suggestions.map(s => <li key={s}>{s}</li>)}</ul></article>)}<p>Orientações para avaliação humana. Dados sintéticos e parâmetros experimentais exigem validação técnica antes de aplicação operacional.</p></>
}

export function Priorities({ mode = 'ranking' }: { mode?: 'ranking' | 'alerts' }) {
  const [search, setSearch] = useSearchParams()
  const date = search.get('reference_date') || ''
  const [classification, setClassification] = useState('')
  const [sector, setSector] = useState('')
  const [municipality, setMunicipality] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ page: String(page), page_size: '10' })
  if (date) params.set('reference_date', date)
  if (classification) params.set('classification', classification)
  if (sector) params.set('sector_id', sector)
  if (municipality) params.set('municipality', municipality)
  const sectors = useQuery({ queryKey: ['priority-sectors'], queryFn: ({ signal }) => getAllPages<{ id: string; name: string }>('/api/v1/sectors', signal) })
  const path = `/api/v1/${mode === 'alerts' ? 'alerts' : 'risks/wells'}?${params}`
  const query = useQuery({ queryKey: ['priorities', path], queryFn: ({ signal }) => getJson<Ranking | (Page<Alert> & { reference_date: string | null })>(path, signal) })
  const effectiveDate = date || query.data?.reference_date || ''
  const detailLink = (risk: Priority) => `/wells/${risk.well_id}${effectiveDate ? `?reference_date=${effectiveDate}` : ''}`
  return <section className="card priority-section"><h2>{mode === 'alerts' ? 'Central de alertas' : 'Priorização de Investigação'}</h2><p>Índice experimental 0–100; cobertura indica disponibilidade de dados. Requer avaliação técnica humana.</p><div className="filters"><label>Data de referência (UTC)<input type="date" value={date} onChange={e => { const next = new URLSearchParams(search); e.target.value ? next.set('reference_date', e.target.value) : next.delete('reference_date'); setSearch(next); setPage(1) }} /></label><select aria-label="Classificação" value={classification} onChange={e => { setClassification(e.target.value); setPage(1) }}><option value="">Todas as classificações</option>{Object.entries(priorityLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><select aria-label="Setor" value={sector} onChange={e => { setSector(e.target.value); setPage(1) }}><option value="">Todos os setores</option>{sectors.data?.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select><input aria-label="Município" placeholder="Município exato" value={municipality} onChange={e => { setMunicipality(e.target.value); setPage(1) }} /></div>
    {query.isPending ? <p role="status">Calculando prioridades…</p> : query.isError ? <div role="alert"><p>Não foi possível consultar as avaliações.</p><button onClick={() => void query.refetch()}>Tentar novamente</button></div> : query.data && <>
      <p>Data da avaliação: {query.data.reference_date || 'Sem medições'}</p>
      {'distribution' in query.data && <><div className="stat-grid"><div className="stat-card"><small>Avaliados</small><strong>{query.data.evaluated}</strong></div><div className="stat-card"><small>Dados insuficientes · não avaliados</small><strong>{query.data.insufficient}</strong></div><div className="stat-card"><small>Alta / crítica</small><strong>{query.data.high_priority}</strong></div></div><p>{Object.entries(query.data.distribution).map(([key, count]) => `${priorityLabels[key as keyof typeof priorityLabels]}: ${count}`).join(' · ')} · Contagens dos filtros aplicados</p></>}
      {query.data.items.length === 0 && <p>Nenhum resultado para esta consulta.</p>}
      {query.data.items.map(item => { const risk = 'evaluation' in item ? item.evaluation : item; return <article className="indicator-card priority-row" key={risk.well_id}><Link to={detailLink(risk)}><b>{risk.well_code}</b> · Ver detalhes</Link><span style={{ color: priorityColors[risk.classification || 'INSUFFICIENT_DATA'] }}>{priorityName(risk)} · {risk.score == null ? 'Não avaliado' : `${risk.score.toFixed(2)} / 100`}</span><small>{risk.municipality || 'Município não informado'} · {risk.sector_code || 'Sem setor'} · Cobertura {(risk.coverage * 100).toFixed(0)}%</small><small>Origem: {risk.data_classification === 'SIMULATED' ? 'Dados simulados' : risk.data_classification} · {risk.source} · {risk.model_version}</small>{risk.factors.filter(f => (f.contribution || 0) > 0).slice(0, 3).map(f => <p key={f.name}>{f.name}: {f.explanation}</p>)}{'message' in item && <><p>{item.kind === 'DATA_QUALITY' ? 'Qualidade de dados' : 'Investigação'}: {item.message}</p><RecommendationList items={risk.recommendations} /></>}</article> })}
      <div className="pagination"><button disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page} de {query.data.pages || 1}</span><button disabled={page >= query.data.pages} onClick={() => setPage(page + 1)}>Próxima</button></div>
    </>}
  </section>
}
