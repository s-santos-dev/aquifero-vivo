import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, NavLink, Outlet, Route, Routes, useNavigate, useSearchParams } from 'react-router-dom'
import L, { type Marker as LeafletMarker } from 'leaflet'
import { GeoJSON, MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import type { GeoJsonObject } from 'geojson'

import { priorityLabels, priorityColors, priorityName, type Priority } from './Priorities'
import { getAllPages, getJson, type Page } from './api'
const MeasurementHistory = lazy(() => import('./MeasurementHistory').then((module) => ({ default: module.MeasurementHistory })))

type PointGeometry = { type: 'Point'; coordinates: [number, number] }
type MultiPolygonGeometry = { type: 'MultiPolygon'; coordinates: number[][][][] }
type Well = { data_classification: string; is_synthetic: boolean; source: string | null; id: string; code: string; name: string; location: PointGeometry; municipality: string | null; state: string | null; depth_m: string | number | null; is_active: boolean; updated_at: string }
type Sector = { id: string; code: string; name: string; description: string | null; boundary: MultiPolygonGeometry }
type Filters = { municipality: string; sectorId: string; status: 'all' | 'active' | 'inactive' }

function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
    map: <><path d="m3 6 5-3 8 3 5-3v15l-5 3-8-3-5 3Z"/><path d="M8 3v15M16 6v15"/></>,
    well: <><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v4M22 12h-4M12 22v-4M2 12h4"/></>,
    layers: <><path d="m12 2 9 5-9 5-9-5Z"/><path d="m3 12 9 5 9-5M3 17l9 5 9-5"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.08A1.7 1.7 0 0 0 8.94 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15 1.7 1.7 0 0 0 3 14H3v-4h.08A1.7 1.7 0 0 0 4.6 8.94a1.7 1.7 0 0 0-.34-1.88L4.2 7l2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V3h4v.08A1.7 1.7 0 0 0 15.06 4.6a1.7 1.7 0 0 0 1.88-.34L17 4.2 19.83 7l-.06.06A1.7 1.7 0 0 0 19.4 9c.18.62.7 1.03 1.53 1.03H21v4h-.08A1.7 1.7 0 0 0 19.4 15Z"/></>,
    filter: <path d="M4 5h16M7 12h10M10 19h4"/>, chevron: <path d="m9 18 6-6-6-6"/>, close: <path d="M18 6 6 18M6 6l12 12"/>,
    retry: <><path d="M20 12a8 8 0 1 1-2.34-5.66L20 8"/><path d="M20 3v5h-5"/></>, pin: <><path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="3"/></>,
  }
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

const markerIcons = Object.fromEntries(Object.entries(priorityColors).map(([key, color]) => [key, L.divIcon({ className: '', html: `<span class="well-marker" style="background:${color};border-color:${color}"><span></span></span>`, iconSize: [28, 28], iconAnchor: [14, 14], popupAnchor: [0, -15] })]))

function MapViewport({ wells, selected }: { wells: Well[]; selected: Well | null }) {
  const map = useMap()
  useEffect(() => {
    if (selected) { const [lng, lat] = selected.location.coordinates; map.flyTo([lat, lng], Math.max(map.getZoom(), 13), { duration: 0.65 }); return }
    if (!wells.length) return
    const bounds = L.latLngBounds(wells.map((well) => [well.location.coordinates[1], well.location.coordinates[0]] as [number, number]))
    map.fitBounds(bounds, { padding: [42, 42], maxZoom: 13 })
  }, [map, selected, wells])
  return null
}

function WellMapMarker({ well, risk, selected, onSelect }: { risk: Priority; well: Well; selected: boolean; onSelect: () => void }) {
  const navigate = useNavigate()
  const marker = useRef<LeafletMarker>(null)
  useEffect(() => { if (selected) marker.current?.openPopup() }, [selected])
  const [lng, lat] = well.location.coordinates
  return <Marker ref={marker} position={[lat, lng]} icon={markerIcons[risk.classification || 'INSUFFICIENT_DATA']} eventHandlers={{ click: onSelect }}><Popup className="well-popup" minWidth={240}><div className="popup-card"><div className="popup-head"><span className={`status-dot ${well.is_active ? 'active' : 'inactive'}`} /><span>{well.is_active ? 'Em operação' : 'Inativo'}</span></div><strong>{well.name}</strong><small>{well.code}{well.is_synthetic ? " · SIMULADO — não representa poço real" : ""}</small><p>{priorityName(risk)} · Índice experimental: {risk.score == null ? 'Não avaliado' : `${risk.score.toFixed(2)} / 100`}</p><p>Setor: {risk.sector_code || 'Sem setor'} · Cobertura: {(risk.coverage * 100).toFixed(0)}%</p><p>Referência: {risk.reference_date || 'Sem medições'}</p><p>{risk.factors.find(f => (f.contribution || 0) > 0)?.name || 'Sem fator contribuinte avaliado'}</p><div className="popup-grid"><span><em>Município</em>{well.municipality || 'Não informado'}</span><span><em>Profundidade</em>{well.depth_m == null ? '—' : `${Number(well.depth_m).toLocaleString('pt-BR')} m`}</span></div><button className="popup-link" onClick={() => navigate(`/wells/${well.id}${risk.reference_date ? `?reference_date=${risk.reference_date}` : ''}`)}>Ver detalhes</button></div></Popup></Marker>
}

function EmptyState({ filtered }: { filtered: boolean }) {
  return <div className="state-card empty-state"><span className="state-icon"><Icon name="pin" size={26} /></span><h2>Nenhum poço encontrado</h2><p>{filtered ? 'Ajuste os filtros para ampliar a busca.' : 'A API ainda não possui poços cadastrados.'}</p></div>
}

export function MapPage() {
  const [search, setSearch] = useSearchParams()
  const referenceDate = search.get('reference_date') || ''
  const [classification, setClassification] = useState('')
  const riskPath = `/api/v1/risks/wells${referenceDate ? `?reference_date=${referenceDate}` : ''}`
  const riskQuery = useQuery({ queryKey: ['map-risks', riskPath], queryFn: async ({ signal }) => {
    const first = await getJson<Page<Priority> & { reference_date: string | null }>(`${riskPath}${riskPath.includes('?') ? '&' : '?'}page_size=100`, signal)
    if (first.pages <= 1) return first.items
    const rest = await getAllPages<Priority>(`/api/v1/risks/wells?reference_date=${first.reference_date}`, signal)
    return rest
  }, retry: 1 })
  const riskById = new Map((riskQuery.data || []).map(r => [r.well_id, r]))
  const [filters, setFilters] = useState<Filters>({ municipality: '', sectorId: '', status: 'all' })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const sectorsQuery = useQuery({ queryKey: ['sectors'], queryFn: ({ signal }) => getAllPages<Sector>('/api/v1/sectors', signal), retry: 1 })
  const allWellsQuery = useQuery({ queryKey: ['wells', 'catalog'], queryFn: ({ signal }) => getAllPages<Well>('/api/v1/wells', signal), retry: 1 })
  const queryString = useMemo(() => { const params = new URLSearchParams(); if (filters.municipality) params.set('municipality', filters.municipality); if (filters.status !== 'all') params.set('is_active', String(filters.status === 'active')); const value = params.toString(); return value ? `/api/v1/wells?${value}` : '/api/v1/wells' }, [filters])
  const wellsQuery = useQuery({ queryKey: ['wells', queryString], queryFn: ({ signal }) => getAllPages<Well>(queryString, signal), retry: 1 })
  const wells = (wellsQuery.data ?? []).filter(well => { const risk = riskById.get(well.id); return risk && (!classification || (risk.classification || risk.status) === classification) && (!filters.sectorId || risk.sector_id === filters.sectorId) })
  const municipalities = useMemo(() => [...new Set((allWellsQuery.data ?? []).map((well) => well.municipality).filter((item): item is string => Boolean(item)))].sort((a, b) => a.localeCompare(b, 'pt-BR')), [allWellsQuery.data])
  const selectedWell = wells.find((well) => well.id === selectedId) ?? null
  const activeCount = wells.filter((well) => well.is_active).length
  const inactiveCount = wells.length - activeCount
  const hasFilters = Boolean(classification || filters.municipality || filters.sectorId || filters.status !== 'all')
  const selectedSector = sectorsQuery.data?.find((sector) => sector.id === filters.sectorId) ?? null
  useEffect(() => { if (selectedId && !wells.some((well) => well.id === selectedId)) setSelectedId(null) }, [selectedId, wells])
  const clearFilters = () => { setClassification(''); setFilters({ municipality: '', sectorId: '', status: 'all' }) }
  const isError = riskQuery.isError || wellsQuery.isError || sectorsQuery.isError || allWellsQuery.isError

  return <section className={`dashboard ${selectedWell || selectedSector ? 'with-history' : ''}`} id="mapa"><div className="filter-bar"><div className="filter-title"><span><Icon name="filter" /></span><div><b>Filtros do mapa</b><small>Refine os poços exibidos</small></div></div><button className="mobile-filter-toggle" onClick={() => setFiltersOpen((open) => !open)}><Icon name="filter" />Filtros {hasFilters && <i />}</button><div className={`filter-fields ${filtersOpen ? 'open' : ''}`}><label><span>Data de referência (UTC)</span><input type="date" value={referenceDate} onChange={e => { const next = new URLSearchParams(search); e.target.value ? next.set('reference_date', e.target.value) : next.delete('reference_date'); setSearch(next) }} /></label><label><span>Classificação</span><select value={classification} onChange={e => setClassification(e.target.value)}><option value="">Todas as classificações</option>{Object.entries(priorityLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label><span>Município</span><select value={filters.municipality} onChange={(event) => setFilters((current) => ({ ...current, municipality: event.target.value }))} disabled={allWellsQuery.isPending}><option value="">Todos os municípios</option>{municipalities.map((municipality) => <option key={municipality}>{municipality}</option>)}</select></label><label><span>Setor</span><select value={filters.sectorId} onChange={(event) => setFilters((current) => ({ ...current, sectorId: event.target.value }))} disabled={sectorsQuery.isPending}><option value="">Todos os setores</option>{sectorsQuery.data?.map((sector) => <option key={sector.id} value={sector.id}>{sector.name}</option>)}</select></label><label><span>Status</span><select value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value as Filters['status'] }))}><option value="all">Todos os status</option><option value="active">Em operação</option><option value="inactive">Inativos</option></select></label>{hasFilters && <button className="clear-button" onClick={clearFilters}><Icon name="close" size={16} />Limpar</button>}</div></div>
        <div className="content-grid"><div className="map-card">
          {isError ? <div className="map-state"><div className="state-card"><span className="state-icon error"><Icon name="retry" size={26} /></span><h2>Não foi possível carregar o mapa</h2><p>Verifique se a FastAPI está disponível e tente novamente.</p><button onClick={() => { void riskQuery.refetch(); void wellsQuery.refetch(); void sectorsQuery.refetch(); void allWellsQuery.refetch() }}><Icon name="retry" size={17} />Tentar novamente</button></div></div> : <MapContainer center={[-5.1, -39.4]} zoom={7} zoomControl attributionControl className="leaflet-map"><TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />{selectedSector && <GeoJSON key={selectedSector.id} data={selectedSector.boundary as GeoJsonObject} style={{ color: '#087f5b', weight: 2, opacity: 0.8, fillColor: '#34d399', fillOpacity: 0.12 }} />}{wells.map((well) => <WellMapMarker key={well.id} well={well} risk={riskById.get(well.id)!} selected={well.id === selectedId} onSelect={() => setSelectedId(well.id)} />)}<MapViewport wells={wells} selected={selectedWell} /></MapContainer>}
          {!isError && (wellsQuery.isPending || riskQuery.isPending) && <div className="loading-overlay"><span className="loader" /><b>Carregando poços...</b><small>Consultando dados geoespaciais</small></div>}{!isError && !(wellsQuery.isPending || riskQuery.isPending) && wells.length === 0 && <div className="map-state transparent"><EmptyState filtered={hasFilters} /></div>}{!isError && !(wellsQuery.isPending || riskQuery.isPending) && wells.length > 0 && <div className="map-legend"><span>Referência: {riskQuery.data?.[0]?.reference_date || 'Sem medições'}</span>{Object.entries(priorityLabels).map(([key, label]) => <span key={key}><i style={{ background: priorityColors[key as keyof typeof priorityColors] }} />{label}</span>)}</div>}</div>
          <aside className="side-panel"><div className="summary-head"><div><span>POÇOS VISÍVEIS</span><strong>{(wellsQuery.isPending || riskQuery.isPending) ? '—' : wells.length.toLocaleString('pt-BR')}</strong></div><span className="summary-icon"><Icon name="well" size={24} /></span></div><div className="status-summary"><div><span><i className="active" />Em operação</span><b>{(wellsQuery.isPending || riskQuery.isPending) ? '—' : activeCount}</b></div><div><span><i className="inactive" />Inativos</span><b>{(wellsQuery.isPending || riskQuery.isPending) ? '—' : inactiveCount}</b></div></div><div className="list-head"><div><b>Poços no mapa</b><small>{hasFilters ? 'Resultado dos filtros aplicados' : 'Selecione para ver detalhes'}</small></div>{hasFilters && <button onClick={clearFilters}>Limpar</button>}</div><div className="well-list">{(wellsQuery.isPending || riskQuery.isPending) ? Array.from({ length: 5 }, (_, index) => <div className="well-row skeleton" key={index}><i /><span><b /><small /></span></div>) : wells.length === 0 ? <EmptyState filtered={hasFilters} /> : wells.map((well) => <button key={well.id} className={`well-row ${selectedId === well.id ? 'selected' : ''}`} onClick={() => setSelectedId(well.id)}><span className={`row-icon ${well.is_active ? 'active' : 'inactive'}`}><Icon name="well" size={18} /></span><span className="row-content"><b>{well.name}</b><small>{well.code} · {well.municipality || 'Município não informado'}</small></span><span className={`row-status ${well.is_active ? 'active' : 'inactive'}`}>{well.is_active ? 'Operando' : 'Inativo'}</span><Icon name="chevron" size={17} /></button>)}</div><footer className="panel-footer"><span><i />{wells.some((well) => well.is_synthetic) ? "Dados sintéticos: não usar em decisões reais" : "Dados carregados da FastAPI"}</span><small>{wellsQuery.dataUpdatedAt ? `Atualizado às ${new Date(wellsQuery.dataUpdatedAt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}` : 'Aguardando atualização'}</small></footer></aside>
        </div>{(selectedWell || selectedSector) && <Suspense fallback={<p role="status">Carregando painel de histórico…</p>}><MeasurementHistory key={`${selectedWell?.id ?? ''}:${selectedSector?.id ?? ''}`} well={selectedWell} sector={selectedSector} /></Suspense>}</section>
}

function AppLayout() {
  return <div className="app-shell"><aside className="admin-nav"><div className="brand"><span className="brand-mark"><i /><i /><i /></span><span><b>Aquífero</b><small>Vivo</small></span></div><nav aria-label="Navegação principal"><NavLink to="/dashboard"><Icon name="grid" />Visão geral</NavLink><NavLink to="/map"><Icon name="map" />Mapa de poços</NavLink><NavLink to="/wells"><Icon name="well" />Poços</NavLink><NavLink to="/sectors"><Icon name="layers" />Setores</NavLink><NavLink to="/alerts"><Icon name="bell" />Alertas</NavLink></nav><div className="nav-footer"><span className="nav-disabled"><Icon name="settings" />Configurações</span><div className="user-card"><span>AV</span><p><b>Administrador</b><small>Gestão hídrica</small></p></div></div></aside><main className="workspace"><header className="topbar"><div><p>Monitoramento territorial</p><h1>Aquífero Vivo</h1></div><div className="top-actions"><span className="api-status"><i />Dados da API</span><button className="icon-button" disabled title="Notificações em desenvolvimento" aria-label="Notificações indisponíveis"><Icon name="bell" /></button><span className="avatar">AV</span></div></header><Outlet /></main></div>
}

export default function App() {
  const Pages = lazy(() => import('./Pages'))
  return <Routes><Route element={<AppLayout />}><Route path="/map" element={<MapPage />} /><Route path="*" element={<Suspense fallback={<p className="page-state">Carregando…</p>}><Pages /></Suspense>} /></Route></Routes>
}
