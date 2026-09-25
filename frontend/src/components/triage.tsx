// Triage-specific building blocks (spec section 14). Pages compose these; keep them presentational.
import { BookMarked, Info, Scale, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ConfidenceDetail, Evidence, Facts, Level, ReferenceData, Route } from '../api/types'
import { FIELD_METHODS, METHOD_BLURB, METHOD_LABEL, type FieldKey, type Method } from './fields'
import { Pill } from './ui'

const METHOD_STYLE: Record<Method, { cls: string; icon: typeof Sparkles }> = {
  ai: { cls: 'bg-ai-soft text-ai', icon: Sparkles },
  rules: { cls: 'bg-emerald-50 text-emerald-700', icon: Scale },
  lookup: { cls: 'bg-slate-100 text-slate-600', icon: BookMarked },
}

/** "AI reads" / "Rule" / "Lookup" tag with an (i) that explains exactly how the field is produced. */
export function MethodTag({ field, compact = false, align = 'left' }: { field: FieldKey; compact?: boolean; align?: 'left' | 'right' }) {
  const { method, how } = FIELD_METHODS[field]
  const { cls, icon: Icon } = METHOD_STYLE[method]
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    window.addEventListener('mousedown', close)
    return () => window.removeEventListener('mousedown', close)
  }, [open])
  return (
    <span ref={ref} className="relative inline-flex items-center gap-0.5 align-middle">
      <span className={`inline-flex items-center gap-0.5 rounded px-1 py-px text-[10px] font-semibold tracking-wide uppercase ${cls}`}>
        <Icon size={9} />{compact ? METHOD_LABEL[method].split(' ')[0] : METHOD_LABEL[method]}
      </span>
      <button type="button" aria-label={`How is ${field.replace('_', ' ')} calculated?`} onClick={() => setOpen((v) => !v)}
        className="rounded-full p-0.5 text-slate-400 hover:text-accent focus-visible:outline-2 focus-visible:outline-accent">
        <Info size={12} />
      </button>
      {open && (
        <span role="tooltip" className={`absolute top-full ${align === 'right' ? 'right-0' : 'left-0'} z-40 mt-1 w-72 rounded-lg border border-line bg-surface p-3 text-left text-xs leading-relaxed font-normal normal-case tracking-normal text-ink shadow-pop`}>
          <span className={`mb-1 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${cls}`}><Icon size={10} />{METHOD_LABEL[method]}</span>
          <span className="block">{how}</span>
          <span className="mt-1.5 block text-muted">{METHOD_BLURB[method]}</span>
        </span>
      )}
    </span>
  )
}

/** Legend for the three ways a value is produced. */
export function MethodLegend() {
  return (
    <span className="inline-flex flex-wrap items-center gap-2 text-[11px] text-muted">
      {(['ai', 'rules', 'lookup'] as Method[]).map((m) => {
        const { cls, icon: Icon } = METHOD_STYLE[m]
        return <span key={m} title={METHOD_BLURB[m]} className={`inline-flex items-center gap-0.5 rounded px-1 py-px text-[10px] font-semibold uppercase ${cls}`}><Icon size={9} />{METHOD_LABEL[m]}</span>
      })}
      <span>· tap (i) for how</span>
    </span>
  )
}

const LEVEL_SHORT: Record<Level, string> = { Highest: 'Hst', High: 'Hi', Medium: 'Med', Low: 'Lo', Lowest: 'Lst' }

/** Thin bar for the 0–1 priority score (orders tickets inside the same priority). */
export function ScoreBar({ score }: { score?: number | null }) {
  if (score == null) return null
  return (
    <span className="ml-1.5 inline-block h-1 w-10 rounded bg-slate-200 align-middle" title={`priority score ${score.toFixed(3)}`}>
      <span className="block h-1 rounded bg-slate-800" style={{ width: `${Math.round(score * 100)}%` }} />
    </span>
  )
}

function formatRemaining(ms: number): string {
  const abs = Math.abs(ms)
  const h = Math.floor(abs / 3_600_000)
  const m = Math.floor((abs % 3_600_000) / 60_000)
  const text = h >= 48 ? `${Math.floor(h / 24)} d` : h >= 1 ? `${h}:${String(m).padStart(2, '0')} h` : `${m} min`
  return ms < 0 ? `overdue ${text}` : `${text} left`
}

/** Live SLA countdown: neutral, amber after 75% of the target, red when overdue. */
export function SlaTimer({ dueAt, startAt, closed = false }: { dueAt?: string | null; startAt?: string | null; closed?: boolean }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(id)
  }, [])
  if (closed) return <span className="text-slate-400" title="Done: the SLA clock has stopped">–</span>
  if (!dueAt) return <span className="text-slate-400">–</span>
  const due = new Date(dueAt).getTime()
  const start = startAt ? new Date(startAt).getTime() : due
  const used = due > start ? (now - start) / (due - start) : 0
  const color = now > due ? 'text-red-700 font-semibold' : used > 0.75 ? 'text-amber-700 font-semibold' : 'text-slate-600'
  return <span className={`tabular-nums whitespace-nowrap ${color}`}>{formatRemaining(due - now)}</span>
}

function confidenceColor(value: number) {
  return value >= 0.8 ? 'bg-emerald-600' : value >= 0.5 ? 'bg-amber-500' : 'bg-red-600'
}

/** Confidence meter; hover shows the breakdown and names the weakest part. */
export function ConfidenceMeter({ value, detail }: { value?: number | null; detail?: ConfidenceDetail | null }) {
  if (value == null) return <span className="text-slate-400">–</span>
  const title = detail
    ? `Votes ${detail.votes.toFixed(2)} · Similar past case ${detail.retrieval.toFixed(2)}${detail.flags.length ? ` · Flags: ${detail.flags.join(', ')}` : ''}`
    : undefined
  return (
    <span className="inline-flex items-center gap-1.5" title={title}>
      <span className="inline-block h-1.5 w-12 overflow-hidden rounded bg-slate-200">
        <span className={`block h-1.5 ${confidenceColor(value)}`} style={{ width: `${Math.round(value * 100)}%` }} />
      </span>
      <span className="tabular-nums text-xs text-slate-700">{Math.round(value * 100)}</span>
    </span>
  )
}

const ROUTE_STYLES: Record<Route, [string, string]> = {
  // The route only says how closely the analyst should look; every ticket still needs their decision.
  auto: ['bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200', 'high confidence'],
  review: ['bg-amber-50 text-amber-800 ring-1 ring-amber-200', 'check carefully'],
  triage: ['bg-red-50 text-red-700 ring-1 ring-red-200', 'low confidence'],
}

export function RoutePill({ route }: { route?: Route | null }) {
  if (!route) return null
  const [cls, label] = ROUTE_STYLES[route]
  return <Pill className={cls}>{label}</Pill>
}

/** Shows `intake → AI value` in violet when the AI changed it. */
export function FieldDiff({ intake, value }: { intake?: string | null; value?: string | null }) {
  if (!value) return <span className="text-slate-400">–</span>
  if (!intake || intake === value) return <span>{value}</span>
  return (
    <span title={`Changed from intake: ${intake}`}>
      <span className="text-slate-400 line-through">{intake}</span> <span className="font-medium text-ai">→ {value}</span>
    </span>
  )
}

const FACT_LABELS: Record<keyof Facts, string> = {
  scope: 'scope',
  outage_extent: 'outage',
  workaround: 'workaround',
  regulatory_or_security: 'regulatory',
  deadline_pressure: 'deadline',
}

export function FactChips({ facts }: { facts?: Facts | null }) {
  if (!facts) return null
  return (
    <div className="flex flex-wrap gap-1">
      {(Object.keys(FACT_LABELS) as (keyof Facts)[]).map((key) => {
        const value = facts[key]
        const text = typeof value === 'boolean' ? (value ? 'yes' : 'no') : value.replaceAll('_', ' ')
        return (
          <span key={key} className="rounded-full border border-line bg-surface px-2 py-0.5 text-xs">
            <span className="text-slate-500">{FACT_LABELS[key]}</span> <b className="font-medium">{text}</b>
          </span>
        )
      })}
    </div>
  )
}

/** 5x5 Urgency x Impact matrix with the chosen cell highlighted. */
export function MatrixGrid({ reference, urgency, impact }: { reference?: ReferenceData; urgency?: Level; impact?: Level }) {
  if (!reference) return null
  const levels = reference.levels
  return (
    <div className="grid grid-cols-6 gap-px text-center text-[10px]" aria-label="Priority matrix">
      <span className="text-slate-400">U\I</span>
      {levels.map((i) => (
        <span key={i} className={`font-semibold ${i === impact ? 'text-slate-900' : 'text-slate-400'}`}>{LEVEL_SHORT[i]}</span>
      ))}
      {levels.map((u) => (
        <div key={u} className="contents">
          <span className={`font-semibold ${u === urgency ? 'text-slate-900' : 'text-slate-400'}`}>{LEVEL_SHORT[u]}</span>
          {levels.map((i) => {
            const hit = u === urgency && i === impact
            return (
              <span key={i} className={`rounded-sm py-0.5 ${hit ? 'bg-ink font-bold text-white shadow-pop' : 'bg-slate-100 text-slate-600'}`}>
                {LEVEL_SHORT[reference.priority_matrix[u][i]]}
              </span>
            )
          })}
        </div>
      ))}
    </div>
  )
}

const KIND_LABEL: Record<Evidence['kind'], [string, string]> = {
  playbook: ['playbook', 'bg-accent-soft text-accent'],
  service_card: ['service', 'bg-slate-100 text-slate-700'],
  historical_ticket: ['learned', 'bg-ai-soft text-ai'],
}

export function EvidenceList({ evidence, highlight }: { evidence: Evidence[]; highlight?: string | null }) {
  const [open, setOpen] = useState<string | null>(null)
  return (
    <ul className="flex flex-col gap-2 text-sm">
      {evidence.map((e) => {
        const [label, cls] = KIND_LABEL[e.kind]
        return (
          <li key={e.ref_id} className={`rounded-md p-2 ${e.ref_id === highlight ? 'bg-accent-soft ring-1 ring-accent/30' : ''}`}>
            <button type="button" className="w-full text-left" onClick={() => setOpen(open === e.ref_id ? null : e.ref_id)}>
              <span className="flex items-center gap-2">
                <Pill className={cls}>{label}</Pill>
                <span className="font-mono text-xs text-slate-500" title={e.similarity != null ? 'Cosine similarity to this ticket' : 'Keyword rank score'}>
                  {e.similarity != null ? `${Math.round(e.similarity * 100)}% match` : e.score.toFixed(2)}
                </span>
                {e.ref_id === highlight && <span className="text-xs font-medium text-accent">used for this proposal</span>}
              </span>
              <span className="mt-0.5 block">{e.title}</span>
            </button>
            {open === e.ref_id && <p className="mt-1 text-xs text-slate-600">{e.snippet}</p>}
          </li>
        )
      })}
    </ul>
  )
}
