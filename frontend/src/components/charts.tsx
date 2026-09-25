// Small SVG chart kit for the Impact dashboard (no chart library).
// Marks follow the dataviz spec: 2px lines + 10% area wash, <=24px columns with 4px
// rounded tops and 2px surface gaps, hairline solid grid, crosshair + tooltip on lines,
// per-column tooltips, legends for 2+ series. Series colors come from SERIES (validated).
import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { SERIES } from './styles'

const GRID = '#e3e8ef'
const TEXT = '#5e6878'
const SURFACE = '#ffffff'

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(600)
  useLayoutEffect(() => {
    if (!ref.current) return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}

function niceMax(v: number) {
  if (v <= 0) return 1
  const step = 10 ** Math.floor(Math.log10(v))
  return Math.ceil(v / step) * step
}

const shortDay = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString([], { day: 'numeric', month: 'short' })

function Tooltip({ x, y, width, children }: { x: number; y: number; width: number; children: ReactNode }) {
  const left = Math.min(Math.max(x - 80, 0), width - 160)
  return (
    <div className="pointer-events-none absolute z-10 w-40 rounded-lg border border-line bg-surface px-2.5 py-2 text-xs shadow-pop" style={{ left, top: Math.max(y - 70, 0) }}>
      {children}
    </div>
  )
}

export function Legend({ items }: { items: { label: string; color: string; kind?: 'rect' | 'line' }[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5">
          {i.kind === 'line'
            ? <span className="inline-block h-0.5 w-3.5 rounded" style={{ background: i.color }} />
            : <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: i.color }} />}
          {i.label}
        </span>
      ))}
    </div>
  )
}

/** Single-series line over days, with area wash, end-point label, crosshair tooltip. */
export function LineChart({ days, values, color = SERIES[0], format, label, maxY }: {
  days: string[]
  values: (number | null)[]
  color?: string
  format: (v: number) => string
  label: string
  maxY?: number
}) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const height = 170
  const pad = { l: 40, r: 44, t: 12, b: 24 }
  const w = width - pad.l - pad.r
  const h = height - pad.t - pad.b
  const top = maxY ?? niceMax(Math.max(0, ...values.filter((v): v is number => v !== null)))
  const x = (i: number) => pad.l + (days.length <= 1 ? 0 : (i / (days.length - 1)) * w)
  const y = (v: number) => pad.t + h - (v / top) * h
  const pts = values.map((v, i) => (v === null ? null : [x(i), y(v)] as const))
  const segments: string[] = []
  let current = ''
  pts.forEach((p) => {
    if (!p) { if (current) segments.push(current); current = ''; return }
    current += `${current ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`
  })
  if (current) segments.push(current)
  const valid = pts.map((p, i) => [p, i] as const).filter(([p]) => p) as [readonly [number, number], number][]
  const area = valid.length > 1
    ? `M${valid[0][0][0]},${pad.t + h}` + valid.map(([p]) => `L${p[0]},${p[1]}`).join('') + `L${valid.at(-1)![0][0]},${pad.t + h}Z`
    : ''
  const last = valid.at(-1)
  const ticks = [0, top / 2, top]

  return (
    <div ref={ref} className="relative" onPointerLeave={() => setHover(null)}>
      <svg width={width} height={height} role="img" aria-label={label}
        onPointerMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const i = Math.round(((e.clientX - rect.left - pad.l) / w) * (days.length - 1))
          setHover(Math.min(Math.max(i, 0), days.length - 1))
        }}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={pad.l + w} y1={y(t)} y2={y(t)} stroke={GRID} strokeWidth={1} />
            <text x={pad.l - 6} y={y(t) + 3} textAnchor="end" fontSize={10} fill={TEXT}>{format(t)}</text>
          </g>
        ))}
        {[0, Math.floor((days.length - 1) / 2), days.length - 1].map((i) => (
          <text key={i} x={x(i)} y={height - 6} textAnchor={i === 0 ? 'start' : i === days.length - 1 ? 'end' : 'middle'} fontSize={10} fill={TEXT}>{shortDay(days[i])}</text>
        ))}
        {area && <path d={area} fill={color} opacity={0.1} />}
        {segments.map((d, i) => <path key={i} d={d} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />)}
        {last && (
          <g>
            <circle cx={last[0][0]} cy={last[0][1]} r={4} fill={color} stroke={SURFACE} strokeWidth={2} />
            <text x={last[0][0] + 7} y={last[0][1] + 3} fontSize={11} fontWeight={600} fill="#0f1a2b">{format(values[last[1]]!)}</text>
          </g>
        )}
        {hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={pad.t + h} stroke={TEXT} strokeWidth={1} opacity={0.4} />
            {values[hover] !== null && <circle cx={x(hover)} cy={y(values[hover]!)} r={4} fill={color} stroke={SURFACE} strokeWidth={2} />}
          </g>
        )}
      </svg>
      {hover !== null && (
        <Tooltip x={x(hover)} y={values[hover] !== null ? y(values[hover]!) : pad.t + h} width={width}>
          <p className="text-sm font-semibold text-ink">{values[hover] === null ? 'no data' : format(values[hover]!)}</p>
          <p className="text-muted">{label} · {shortDay(days[hover])}</p>
        </Tooltip>
      )}
    </div>
  )
}

/** Stacked daily columns for 2-3 series, per-column tooltip, optional table view. */
export function StackedColumns({ days, series }: {
  days: string[]
  series: { label: string; color: string; values: number[] }[]
}) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const height = 190
  const pad = { l: 32, r: 8, t: 10, b: 24 }
  const w = width - pad.l - pad.r
  const h = height - pad.t - pad.b
  const totals = days.map((_, i) => series.reduce((s, ser) => s + ser.values[i], 0))
  const top = niceMax(Math.max(...totals, 1))
  const band = w / days.length
  const barW = Math.min(24, band - 2)
  const y = (v: number) => (v / top) * h
  const ticks = [0, top / 2, top]

  return (
    <div ref={ref} className="relative" onPointerLeave={() => setHover(null)}>
      <svg width={width} height={height} role="img" aria-label="Tickets triaged per day by route">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={pad.l + w} y1={pad.t + h - y(t)} y2={pad.t + h - y(t)} stroke={GRID} strokeWidth={1} />
            <text x={pad.l - 6} y={pad.t + h - y(t) + 3} textAnchor="end" fontSize={10} fill={TEXT}>{Math.round(t)}</text>
          </g>
        ))}
        {days.map((day, i) => {
          const cx = pad.l + band * i + (band - barW) / 2
          let base = pad.t + h
          const visible = series.map((s) => s.values[i]).map((v, k) => [v, k] as const).filter(([v]) => v > 0)
          const topK = visible.at(-1)?.[1]
          return (
            <g key={day} onPointerEnter={() => setHover(i)} opacity={hover === null || hover === i ? 1 : 0.55}>
              <rect x={pad.l + band * i} y={pad.t} width={band} height={h} fill="transparent" />
              {series.map((s, k) => {
                const v = s.values[i]
                if (!v) return null
                const hh = y(v)
                base -= hh
                const gap = k === topK ? 0 : 2 // 2px surface gap between stacked segments
                const r = k === topK ? Math.min(4, barW / 2) : 0
                const path = r
                  ? `M${cx},${base + hh}V${base + r}Q${cx},${base} ${cx + r},${base}H${cx + barW - r}Q${cx + barW},${base} ${cx + barW},${base + r}V${base + hh}Z`
                  : `M${cx},${base + hh}V${base + gap}H${cx + barW}V${base + hh}Z`
                return <path key={s.label} d={path} fill={s.color} />
              })}
            </g>
          )
        })}
        {[0, Math.floor((days.length - 1) / 2), days.length - 1].map((i) => (
          <text key={i} x={pad.l + band * i + band / 2} y={height - 6} textAnchor="middle" fontSize={10} fill={TEXT}>{shortDay(days[i])}</text>
        ))}
      </svg>
      {hover !== null && (
        <Tooltip x={pad.l + band * hover + band / 2} y={pad.t + h - y(totals[hover])} width={width}>
          <p className="text-sm font-semibold text-ink">{totals[hover]} tickets</p>
          <p className="mb-1 text-muted">{shortDay(days[hover])}</p>
          {[...series].reverse().map((s) => (
            <p key={s.label} className="flex items-center gap-1.5">
              <span className="inline-block h-0.5 w-3 rounded" style={{ background: s.color }} />
              <b className="tabular text-ink">{s.values[hover]}</b><span className="text-muted">{s.label}</span>
            </p>
          ))}
        </Tooltip>
      )}
    </div>
  )
}

/** Horizontal bars in HTML; value at the tip, tooltip via title, text in text tokens. */
export function HBars({ rows, color = SERIES[0], format = String }: {
  rows: { label: string; value: number; hint?: string }[]
  color?: string
  format?: (v: number) => string
}) {
  const max = Math.max(1, ...rows.map((r) => r.value))
  return (
    <div className="flex flex-col gap-2">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[9rem_1fr] items-center gap-3 text-sm" title={r.hint ?? `${r.label}: ${format(r.value)}`}>
          <span className="truncate text-muted">{r.label}</span>
          <span className="flex items-center gap-2">
            <span className="h-3 rounded-r" style={{ width: `${(r.value / max) * 85}%`, minWidth: r.value ? 4 : 0, background: color }} />
            <span className="text-xs font-medium tabular text-ink">{format(r.value)}</span>
          </span>
        </div>
      ))}
    </div>
  )
}
