// The live triage walkthrough: one card per pipeline stage, filled in as the stream arrives.
import {
  Brain,
  CheckCircle2,
  Circle,
  Database,
  Gauge,
  Loader2,
  PenLine,
  Scale,
  UserCheck,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'
import type { TriageEvent } from '../api/stream'
import type { AssigneeSuggestion, ConfidenceDetail, Evidence, Facts, Level, ReferenceData, Route } from '../api/types'
import { ConfidenceMeter, FactChips, MatrixGrid, RoutePill } from './triage'
import { Pill, PriorityPill } from './ui'

type Status = 'pending' | 'running' | 'done' | 'failed'

const STAGES: { key: string; title: string; icon: LucideIcon; blurb: string }[] = [
  { key: 'retrieve', title: 'Retrieve precedent', icon: Database, blurb: 'Hybrid search: keywords + meaning' },
  { key: 'extract', title: 'Read the ticket', icon: Brain, blurb: 'Independent votes on the observable facts' },
  { key: 'rubric', title: 'Decide priority', icon: Scale, blurb: 'Deterministic rubric + Urgency × Impact matrix' },
  { key: 'confidence', title: 'Measure confidence', icon: Gauge, blurb: 'Weakest of vote agreement and past-case match' },
  { key: 'assign', title: 'Suggest a specialist', icon: UserCheck, blurb: 'Expert for the problem, balanced by workload; the analyst decides' },
  { key: 'draft', title: 'Draft the resolution', icon: PenLine, blurb: 'Adapted from the closest past solution' },
]

const VOTE_FIELDS: [string, string][] = [
  ['work_type', 'Work type'],
  ['service', 'Service'],
  ['scope', 'Scope'],
  ['outage_extent', 'Outage'],
  ['workaround', 'Workaround'],
  ['regulatory_or_security', 'Regulatory'],
  ['deadline_pressure', 'Deadline'],
  ['resolution', 'Resolution'],
  ['playbook_ref', 'Playbook match'],
]

const fmt = (v: unknown) => (v === null || v === undefined ? '—' : typeof v === 'boolean' ? (v ? 'yes' : 'no') : String(v).replaceAll('_', ' '))

function statusOf(events: TriageEvent[], key: string, running: boolean, failed: boolean): Status {
  if (events.some((e) => e.stage === key && e.status === 'completed')) return 'done'
  if (events.some((e) => e.stage === key && e.status === 'failed')) return 'failed'
  const current = STAGES.find((s) => !events.some((e) => e.stage === s.key && e.status === 'completed'))?.key
  if (key !== current || !events.length) return 'pending'
  return failed ? 'failed' : running ? 'running' : 'pending'
}

function StatusIcon({ status, icon: Icon }: { status: Status; icon: LucideIcon }) {
  const base = 'relative z-10 grid h-9 w-9 shrink-0 place-items-center rounded-full ring-4 ring-canvas'
  if (status === 'done') return <span className={`${base} bg-emerald-500 text-white`}><CheckCircle2 size={18} /></span>
  if (status === 'failed') return <span className={`${base} bg-red-500 text-white`}><XCircle size={18} /></span>
  if (status === 'running') return <span className={`${base} bg-accent text-white`}><Loader2 size={18} className="animate-spin" /></span>
  return <span className={`${base} bg-surface text-slate-400 ring-slate-100`}><Icon size={17} /></span>
}

function Votes({ votes, total, agreement, manual }: { votes: TriageEvent[]; total: number; agreement?: Record<string, number>; manual: string[] }) {
  const answers = votes.filter((v) => v.data.ok).map((v) => v.data.answer as Record<string, unknown>)
  const majority = Object.fromEntries(
    VOTE_FIELDS.map(([f]) => {
      const counts = new Map<string, number>()
      answers.forEach((a) => counts.set(fmt(a[f]), (counts.get(fmt(a[f])) ?? 0) + 1))
      return [f, [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0]]
    }),
  )
  const slots = Array.from({ length: total }, (_, i) => votes.find((v) => v.data.index === i + 1))
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-2 md:grid-cols-3">
        {slots.map((vote, i) => (
          <div key={i} className={`rounded-lg border p-3 text-xs ${vote ? 'animate-rise border-line bg-surface' : 'border-dashed border-line bg-canvas'}`}>
            <p className="mb-2 flex items-center justify-between font-semibold">
              Vote {i + 1}
              {!vote && <span className="flex items-center gap-1 font-normal text-muted"><Loader2 size={12} className="animate-spin" />thinking…</span>}
              {vote && !vote.data.ok && <span className="font-normal text-red-600">failed</span>}
            </p>
            {vote?.data.ok ? (
              <dl className="grid grid-cols-[5.5rem_1fr] gap-x-2 gap-y-1">
                {VOTE_FIELDS.map(([f, label]) => {
                  const value = fmt((vote.data.answer as Record<string, unknown>)[f])
                  const differs = answers.length > 1 && value !== majority[f]
                  return (
                    <div key={f} className="contents">
                      <dt className="text-muted">{label}</dt>
                      <dd className={`truncate ${differs ? 'rounded bg-amber-100 px-1 font-semibold text-amber-900' : ''}`} title={value}>{value}</dd>
                    </div>
                  )
                })}
              </dl>
            ) : vote ? (
              <p className="text-red-700">{String(vote.data.error)}</p>
            ) : (
              <div className="flex flex-col gap-1.5">{VOTE_FIELDS.slice(0, 6).map(([f]) => <span key={f} className="h-3 animate-pulse rounded bg-slate-200/70" />)}</div>
            )}
          </div>
        ))}
      </div>
      {agreement && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-muted">Agreement per field:</span>
          {VOTE_FIELDS.map(([f, label]) => (
            <Pill key={f} className={manual.includes(f) ? 'bg-accent-soft text-accent' : (agreement[f] ?? 0) >= 1 ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-100 text-amber-900'}>
              {label} {manual.includes(f) ? 'set by staff' : `${Math.round((agreement[f] ?? 0) * 100)}%`}
            </Pill>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Walkthrough({ events, running, reference, votesTotal }: {
  events: TriageEvent[]
  running: boolean
  reference?: ReferenceData
  votesTotal: number
}) {
  const get = (stage: string, status = 'completed') => events.find((e) => e.stage === stage && e.status === status)
  const done = get('done')
  const failed = events.find((e) => e.stage === 'error')

  const details: Record<string, ReactNode> = {}
  const retrieve = get('retrieve')
  if (retrieve) {
    const evidence = retrieve.data.evidence as Evidence[]
    const floor = Number(retrieve.data.min_similarity ?? 0.3)
    details.retrieve = (
      <>
      <p className="mb-1.5 text-xs text-muted">
        Only documents at least {Math.round(floor * 100)}% similar to the ticket, and close to the best match, are kept (up to 6).
        {Boolean(retrieve.data.no_precedent) && <b className="ml-1 text-amber-700">No similar past fix: the draft will be first steps, not a resolution.</b>}
      </p>
      <ul className="grid gap-1.5 sm:grid-cols-2">
        {evidence.map((e) => (
          <li key={e.ref_id} className="animate-rise flex items-center gap-2 rounded-lg border border-line px-2.5 py-1.5 text-xs">
            <Pill className={e.kind === 'playbook' ? 'bg-accent-soft text-accent' : e.kind === 'historical_ticket' ? 'bg-ai-soft text-ai' : 'bg-slate-100 text-slate-600'}>
              {e.kind === 'historical_ticket' ? 'learned' : e.kind === 'service_card' ? 'service' : 'playbook'}
            </Pill>
            <span className="min-w-0 flex-1 truncate" title={e.title}>{e.title}</span>
            <span className="font-mono text-muted">{e.similarity != null ? `${Math.round(e.similarity * 100)}%` : e.score.toFixed(2)}</span>
          </li>
        ))}
      </ul>
      </>
    )
  }
  const voteEvents = events.filter((e) => e.stage === 'vote')
  const extract = get('extract')
  if (voteEvents.length || get('extract', 'started')) {
    details.extract = extract?.data.heuristic ? (
      <p className="text-sm text-amber-800">{extract.message}</p>
    ) : (
      <Votes votes={voteEvents} total={votesTotal} agreement={extract?.data.vote_agreement as Record<string, number> | undefined}
        manual={(extract?.data.manual as string[] | undefined) ?? []} />
    )
  }
  const rubric = get('rubric')
  if (rubric) {
    const d = rubric.data as { facts: Facts; impact: Level; urgency: Level; priority: Level; priority_score: number; trace: string[] }
    details.rubric = (
      <div className="grid gap-4 md:grid-cols-[1fr_14rem]">
        <div className="flex flex-col gap-2">
          <FactChips facts={d.facts} />
          <ul className="flex flex-col gap-1 text-sm">{d.trace.map((t) => <li key={t} className="animate-rise">→ {t}</li>)}</ul>
          <p className="flex items-center gap-2 text-sm">Result <PriorityPill level={d.priority} /> <span className="font-mono text-xs text-muted">score {d.priority_score.toFixed(3)}</span></p>
        </div>
        <MatrixGrid reference={reference} urgency={d.urgency} impact={d.impact} />
      </div>
    )
  }
  const conf = get('confidence')
  if (conf) {
    const c = conf.data.confidence as ConfidenceDetail
    details.confidence = (
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        <span className="flex items-center gap-2">Votes agree <ConfidenceMeter value={c.votes} /></span>
        <span className="flex items-center gap-2">Similar past case <ConfidenceMeter value={c.retrieval} /></span>
        <span className="flex items-center gap-2">Flags <b className="font-medium">{c.flags.length ? c.flags.join(', ').replaceAll('_', ' ') : 'none'}</b></span>
        <span className="flex items-center gap-2 font-semibold">Overall {Math.round(c.overall * 100)}% <RoutePill route={conf.data.route as Route} /></span>
        {Boolean(conf.data.escalated) && <Pill className="bg-red-50 text-red-700 ring-1 ring-red-200">escalated to the team lead</Pill>}
      </div>
    )
  }
  const assign = get('assign')
  if (assign) {
    const s = assign.data.suggestion as AssigneeSuggestion
    details.assign = (
      <div className="flex flex-col gap-2 text-sm">
        <p>Expert <b>{s.expert?.split('@')[0] ?? 'none'}</b> · suggested specialist <b>{(assign.data.suggested_assignee as string | null)?.split('@')[0] ?? 'none'}</b> · waiting for the <b>{String(assign.data.waiting_for ?? 'analyst')}</b></p>
        <p className="text-xs text-muted">{s.reason}</p>
        <div className="flex flex-wrap gap-1.5">
          {s.candidates.slice(0, 4).map((c) => (
            <Pill key={c.user} className={c.user === s.recommended ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-slate-100 text-slate-600'}>
              {c.name} · {c.open}/{c.capacity} open · {c.score.toFixed(2)}
            </Pill>
          ))}
        </div>
      </div>
    )
  }
  const draft = get('draft')
  if (draft) {
    details.draft = <blockquote className="animate-rise rounded-lg border-l-4 border-ai bg-ai-soft/60 p-3 text-sm">{String(draft.data.comment)}</blockquote>
  }

  return (
    <ol className="relative flex flex-col gap-4 before:absolute before:top-4 before:bottom-4 before:left-[17px] before:w-0.5 before:bg-line">
      {STAGES.map(({ key, title, icon, blurb }) => {
        const status = statusOf(events, key, running, Boolean(failed))
        const ms = events.find((e) => e.stage === key && e.status === 'completed')?.elapsed_ms
        const message = events.filter((e) => e.stage === key).at(-1)?.message
        return (
          <li key={key} className="relative flex gap-4">
            <StatusIcon status={status} icon={icon} />
            <div className={`min-w-0 flex-1 rounded-xl border bg-surface p-4 shadow-card transition ${status === 'running' ? 'border-accent/40 ring-2 ring-accent/10' : 'border-line'} ${status === 'pending' ? 'opacity-55' : ''}`}>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-semibold">{title} <span className="ml-1 text-xs font-normal text-muted">{blurb}</span></p>
                {ms !== undefined && <span className="font-mono text-xs text-muted">{(ms / 1000).toFixed(1)} s</span>}
              </div>
              {message && <p className="mt-0.5 text-sm text-muted">{message}</p>}
              {details[key] && <div className="mt-3">{details[key]}</div>}
            </div>
          </li>
        )
      })}
      <li className="relative flex gap-4">
        <StatusIcon status={done ? 'done' : failed ? 'failed' : 'pending'} icon={Circle} />
        <p className={`self-center text-sm font-medium ${failed ? 'text-red-700' : done ? 'text-emerald-700' : 'text-muted'}`}>
          {failed ? failed.message : done ? done.message : 'Waiting for the proposal…'}
        </p>
      </li>
    </ol>
  )
}
