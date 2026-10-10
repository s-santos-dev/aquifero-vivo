import { labels, fmt, type Parameters, type Config } from './Simulator'

export default function ScenarioControls({ parameters, config, disabled, editableKeys, onChange }: { parameters: Parameters; config: Config; disabled?: boolean; editableKeys?: (keyof Parameters)[]; onChange: (p: Parameters) => void }) {
  return <div className="scenario-controls">{(Object.keys(labels) as (keyof Parameters)[]).map(key => <label key={key}><span>{labels[key]}: {fmt(parameters[key], '%')}</span><input aria-label={labels[key]} type="range" min={config.min_change_pct} max={config.max_change_pct} value={Number.isFinite(parameters[key]) ? parameters[key] : 0} disabled={disabled || (editableKeys && !editableKeys.includes(key))} onChange={e => onChange({ ...parameters, [key]: Number(e.target.value) })} /><input aria-label={`${labels[key]} percentual`} type="number" min={config.min_change_pct} max={config.max_change_pct} value={Number.isFinite(parameters[key]) ? parameters[key] : ''} disabled={disabled || (editableKeys && !editableKeys.includes(key))} onChange={e => onChange({ ...parameters, [key]: e.target.value === '' ? NaN : Number(e.target.value) })} /></label>)}</div>
}

