import {
  ArrowLeft,
  BookOpen,
  CircleCheck,
  Check,
  ChevronDown,
  ChevronUp,
  Gauge,
  Hourglass,
  History,
  Inbox,
  MessagesSquare,
  Pencil,
  Play,
  PlayCircle,
  Scale,
  Siren,
  Sparkles,
  UserCheck,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useAssignTicket, useLlmModels, useReference, useReviewTriage, useSettings, useTicket, useUsers, useWorkUpdate } from '../api/hooks'
import { useTriageStream } from '../api/stream'
import type { DecisionEdit, Level, ReviewCreate, TicketDetail, TriageResult, WorkUpdate } from '../api/types'
import {
  ConfidenceMeter,
  EvidenceList,
  FactChips,
  FieldDiff,
  MatrixGrid,
  RoutePill,
  ScoreBar,
  SlaTimer,
} from '../components/triage'
import ComposeDialog from '../components/ComposeDialog'
import Walkthrough from '../components/Walkthrough'
import { useCopilot } from '../copilot/context'
import { Button, Card, ErrorBox, Field, Loading, Pill, PriorityPill, StatePill, WorkStatusPill, inputClass } from '../components/ui'
import { HEURISTIC, useSelectedModel } from '../model/context'
import { canDispatch, useViewer } from '../viewas/context'

const short = (email?: string | null) => (email ? email.split('@')[0] : '–')

const StaffBadge = () => <Pill className="ml-1.5 bg-accent-soft text-accent">set by staff</Pill>

function ConfidencePanel({ result }: { result: TriageResult }) {
  const d = result.confidence_detail
  return (
    <Card title={`Confidence ${Math.round(result.confidence * 100)}%`} icon={<Gauge size={15} />} actions={<RoutePill route={result.route} />}>
      {d ? (
        <dl className="flex flex-col gap-2 text-sm">
          <div className="flex items-center justify-between"><dt className="text-muted">Votes agree</dt><dd><ConfidenceMeter value={d.votes} /></dd></div>
          <div className="flex items-center justify-between"><dt className="text-muted">Similar past case</dt><dd><ConfidenceMeter value={d.retrieval} /></dd></div>
          <div className="flex items-center justify-between"><dt className="text-muted">Flags</dt><dd className="text-xs">{d.flags.length ? d.flags.join(', ').replaceAll('_', ' ') : 'none'}</dd></div>
          {result.confidence < 0.8 && (
            <p className="rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs text-amber-900">
              Weakest part: {d.flags.includes('heuristic_fallback') ? 'no LLM result' : d.votes < d.retrieval ? 'the votes disagree' : 'no close past case'}.
            </p>
          )}
        </dl>
      ) : <ConfidenceMeter value={result.confidence} />}
    </Card>
  )
}

function AssigneePanel({ ticket, result }: { ticket: TicketDetail; result: TriageResult }) {
  const assign = useAssignTicket()
  const { user, role } = useViewer()
  const { data: users } = useUsers()
  const s = result.assignee_suggestion
  const canAssign = canDispatch(role) && ticket.work_status !== 'done'
  // Only specialists take work (proposals saved before a roster change may list others).
  const specialists = new Set(users?.filter((u) => u.role === 'specialist').map((u) => u.email))
  const candidates = s?.candidates.filter((c) => !users || specialists.has(c.user)) ?? []
  return (
    <Card title="Specialist" icon={<UserCheck size={15} />}>
      <dl>
        <Field label={ticket.work_status === 'open' ? 'AI suggests' : 'Assigned to'}>
          {ticket.work_status !== 'open' ? <b>{short(ticket.assignee)}</b>
            : s?.recommended ? <><b>{short(s.recommended)}</b> <span className="text-xs text-muted">(not dispatched yet)</span></>
            : <span className="text-red-600">no suggestion</span>}
          {ticket.manual_fields.includes('assignee') && <StaffBadge />}
        </Field>
        <Field label="Expert">{short(s?.expert)} <span className="text-xs text-muted">(export)</span></Field>
      </dl>
      {s && <p className="mt-1 text-xs text-muted">{s.reason}</p>}
      {candidates.length > 0 && (
        <ul className="mt-3 flex flex-col divide-y divide-line rounded-lg border border-line text-xs">
          {candidates.map((c) => {
            const load = c.capacity ? c.open / c.capacity : 0
            return (
              <li key={c.user} className="flex items-center gap-2 px-2.5 py-2">
                <span className="grid h-6 w-6 place-items-center rounded-full bg-canvas text-[10px] font-semibold uppercase">{c.name.split(' ').map((p) => p[0]).join('')}</span>
                <span className="min-w-0 flex-1 truncate">
                  {c.name}{c.user === s?.expert && <span className="ml-1 text-accent">expert</span>}
                </span>
                <span className="inline-block h-1.5 w-10 overflow-hidden rounded bg-slate-200"><span className={`block h-1.5 ${load >= 1 ? 'bg-red-500' : load >= 0.6 ? 'bg-amber-400' : 'bg-emerald-500'}`} style={{ width: `${Math.min(100, load * 100)}%` }} /></span>
                <span className="w-8 text-right tabular">{c.open}/{c.capacity}</span>
                {ticket.assignee === c.user ? <Check size={14} className="text-emerald-600" /> : canAssign && (
                  <button type="button" className="font-medium text-accent hover:underline disabled:opacity-50" disabled={assign.isPending}
                    onClick={() => assign.mutate({ ticketId: ticket.id, assignee: c.user, by: user?.email })}>
                    {ticket.work_status === 'open' ? 'dispatch' : 'reassign'}
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}
      <ErrorBox error={assign.error} />
    </Card>
  )
}

function ProposalPanels({ ticket, result, editing, edits, setEdit }: {
  ticket: TicketDetail
  result: TriageResult
  editing: boolean
  edits: DecisionEdit
  setEdit: <K extends keyof DecisionEdit>(key: K, value: DecisionEdit[K]) => void
}) {
  const { data: ref } = useReference()
  const current = { ...result, ...edits }
  const urgency = current.urgency as Level
  const impact = current.impact as Level
  const priority = ref?.priority_matrix[urgency]?.[impact] ?? result.priority
  const team = ref?.services.find((s) => s.name === current.service)?.team ?? result.team
  const votes = result.vote_agreement
  const staff = (f: string) => ticket.manual_fields.includes(f)

  const select = (key: 'work_type' | 'service' | 'urgency' | 'impact' | 'resolution', options: readonly string[]) => (
    <select id={`edit-${key}`} aria-label={key} value={String(current[key])} onChange={(e) => setEdit(key, e.target.value as never)}
      className="rounded-md border border-line bg-surface px-1.5 py-0.5 text-sm">
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  )
  const voteNote = (field: string) =>
    staff(field) ? <StaffBadge /> : votes[field] !== undefined && votes[field] < 1
      ? <Pill className="ml-1.5 bg-amber-50 text-amber-800">votes {Math.round(votes[field] * 100)}%</Pill> : null
  const row = (label: string, field: 'work_type' | 'service' | 'urgency' | 'impact' | 'resolution', intake: string | null | undefined, options?: readonly string[]) => (
    <Field label={label}>
      {editing && options ? select(field, options) : intake !== undefined ? <FieldDiff intake={intake} value={String(current[field])} /> : String(current[field])}
      {!editing && voteNote(field)}
    </Field>
  )

  return (
    <>
      <Card title={<>AI proposal <span className="font-normal text-muted">· {result.model}</span></>} icon={<Sparkles size={15} />}
        actions={<span className="font-mono text-xs text-muted">{(result.latency_ms / 1000).toFixed(1)} s</span>}>
        <dl className="divide-y divide-line/70">
          {row('Work type', 'work_type', ticket.work_type, ref?.work_types)}
          {row('Service', 'service', ticket.affected_service, ref?.services.map((s) => s.name))}
          <Field label="Team">{team} <span className="text-xs text-muted">(fixed by service)</span></Field>
          {row('Impact', 'impact', ticket.impact, ref?.levels)}
          {row('Urgency', 'urgency', ticket.urgency, ref?.levels)}
          <Field label="Priority">
            <PriorityPill level={priority} /><ScoreBar score={result.priority_score} />
            {ticket.priority && priority !== ticket.priority && <span className="ml-2 text-xs text-muted">was {ticket.priority}</span>}
          </Field>
          {row('Resolution', 'resolution', undefined, ref?.resolutions)}
        </dl>
        <div className="mt-3"><FactChips facts={result.facts} /></div>
        {result.rationale && <p className="mt-3 rounded-lg bg-canvas px-3 py-2 text-xs text-muted">{result.rationale}</p>}
      </Card>

      <Card title="Why this priority" icon={<Scale size={15} />}>
        <div className="grid gap-4 sm:grid-cols-[1fr_13rem]">
          <ul className="flex flex-col gap-1.5 text-sm">
            {(editing ? [`Priority ${priority} = matrix[urgency ${urgency}][impact ${impact}] (edited)`] : result.rubric_trace).map((line) => (
              <li key={line} className="flex gap-2"><span className="text-muted">→</span>{line}</li>
            ))}
          </ul>
          <MatrixGrid reference={ref} urgency={urgency} impact={impact} />
        </div>
      </Card>

      <Card title={<>Suggested resolution{staff('resolution_comment') && <StaffBadge />}</>} icon={<Pencil size={15} />}
        actions={<span className="text-xs text-muted">AI draft</span>}>
        {editing ? (
          <>
            <label className="sr-only" htmlFor="edit-comment">Resolution comment</label>
            <textarea id="edit-comment" rows={5} value={current.resolution_comment} onChange={(e) => setEdit('resolution_comment', e.target.value)} className={inputClass} />
          </>
        ) : (
          <blockquote className="rounded-lg border-l-4 border-ai bg-ai-soft/50 p-3 text-sm leading-relaxed">{current.resolution_comment}</blockquote>
        )}
      </Card>
    </>
  )
}

/** The analyst's decision on the AI proposal. Approving dispatches the ticket to the specialist. */
function DecisionBar({ result, editing, setEditing, edits, reset }: {
  result: TriageResult
  editing: boolean
  setEditing: (v: boolean) => void
  edits: DecisionEdit
  reset: () => void
}) {
  const review = useReviewTriage()
  const { user } = useViewer()
  const [openedAt] = useState(() => Date.now())
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')

  const submit = (action: ReviewCreate['action']) =>
    review.mutate(
      {
        resultId: result.id,
        body: {
          action,
          edits: action === 'edit' ? edits : null,
          notes: action === 'reject' ? reason || null : null,
          reviewer: user?.email ?? 'analyst',
          review_seconds: (Date.now() - openedAt) / 1000,
        },
      },
      { onSuccess: () => { setEditing(false); setRejecting(false); reset() } },
    )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (editing || rejecting || (e.target as HTMLElement).closest('input, textarea, select')) return
      if (e.key === 'a') submit('approve')
      if (e.key === 'e') setEditing(true)
      if (e.key === 'r') setRejecting(true)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  return (
    <div className="sticky bottom-3 z-10 flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface/95 px-4 py-3 shadow-pop backdrop-blur">
      {rejecting ? (
        <>
          <label className="sr-only" htmlFor="reject-reason">Reason</label>
          <input id="reject-reason" autoFocus value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why is the proposal wrong?"
            className={`${inputClass} min-w-0 flex-1`} />
          <Button variant="danger" onClick={() => submit('reject')} disabled={review.isPending}>Reject → Needs review</Button>
          <Button variant="ghost" onClick={() => setRejecting(false)}>Cancel</Button>
        </>
      ) : editing ? (
        <>
          <Button icon={<Check size={15} />} onClick={() => submit('edit')} disabled={review.isPending}>Save & dispatch</Button>
          <Button variant="ghost" onClick={() => { setEditing(false); reset() }}>Cancel</Button>
          <span className="text-xs text-muted">Team and priority are recomputed from service and urgency/impact.</span>
        </>
      ) : (
        <>
          <Button icon={<Check size={15} />} onClick={() => submit('approve')} disabled={review.isPending}>
            Approve & dispatch{result.assignee_suggestion?.recommended ? ` to ${short(result.assignee_suggestion.recommended)}` : ''}
            <kbd className="ml-1 rounded bg-white/20 px-1 text-[10px]">A</kbd>
          </Button>
          <Button variant="secondary" icon={<Pencil size={14} />} onClick={() => setEditing(true)}>Edit <kbd className="ml-1 rounded bg-canvas px-1 text-[10px]">E</kbd></Button>
          <Button variant="secondary" className="text-red-600" icon={<X size={14} />} onClick={() => setRejecting(true)}>Reject <kbd className="ml-1 rounded bg-canvas px-1 text-[10px]">R</kbd></Button>
        </>
      )}
      <span className="ml-auto text-xs text-muted">Deciding as <b className="text-ink">{user?.name ?? '–'}</b></span>
      <div className="w-full"><ErrorBox error={review.error} /></div>
    </div>
  )
}

/** The specialist's controls: start, wait for information, resume, and mark done with a closing note. */
function WorkBar({ ticket, result }: { ticket: TicketDetail; result: TriageResult | null }) {
  const work = useWorkUpdate()
  const { user } = useViewer()
  const { data: ref } = useReference()
  const [mode, setMode] = useState<'idle' | 'wait' | 'resolve'>('idle')
  const [note, setNote] = useState('')
  const [resolution, setResolution] = useState<string>(result?.resolution ?? 'done')
  const [comment, setComment] = useState(result?.resolution_comment ?? '')
  const send = (body: Omit<WorkUpdate, 'by'>) =>
    work.mutate({ ticketId: ticket.id, body: { ...body, by: user?.email ?? '' } }, { onSuccess: () => setMode('idle') })
  const status = ticket.work_status

  return (
    <div className="sticky bottom-3 z-10 flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface/95 px-4 py-3 shadow-pop backdrop-blur">
      {mode === 'resolve' ? (
        <div className="flex w-full flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-sm font-medium" htmlFor="work-resolution">Resolution</label>
            <select id="work-resolution" value={resolution} onChange={(e) => setResolution(e.target.value)}
              className="rounded-md border border-line bg-surface px-2 py-1 text-sm">
              {(ref?.resolutions ?? ['done']).map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <span className="text-xs text-muted">Prefilled with the AI's suggestion: change it to what you actually did.</span>
          </div>
          <label className="sr-only" htmlFor="work-comment">Closing note</label>
          <textarea id="work-comment" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} className={inputClass}
            placeholder="Root cause, what you did, how you verified it" />
          <div className="flex flex-wrap items-center gap-2">
            <Button icon={<CircleCheck size={15} />} disabled={work.isPending || !comment.trim()}
              onClick={() => send({ action: 'resolve', resolution: resolution as WorkUpdate['resolution'], resolution_comment: comment })}>
              Mark done
            </Button>
            <Button variant="ghost" onClick={() => setMode('idle')}>Cancel</Button>
            <span className="text-xs text-muted">Done tickets are added to the knowledge base, so the next similar ticket finds your fix.</span>
          </div>
        </div>
      ) : mode === 'wait' ? (
        <>
          <label className="sr-only" htmlFor="work-note">What's missing</label>
          <input id="work-note" autoFocus value={note} onChange={(e) => setNote(e.target.value)} placeholder="What information are you waiting for?"
            className={`${inputClass} min-w-0 flex-1`} />
          <Button variant="secondary" icon={<Hourglass size={14} />} disabled={work.isPending} onClick={() => send({ action: 'wait', note: note || null })}>Set waiting</Button>
          <Button variant="ghost" onClick={() => setMode('idle')}>Cancel</Button>
        </>
      ) : (
        <>
          {status === 'assigned' && <Button icon={<PlayCircle size={15} />} disabled={work.isPending} onClick={() => send({ action: 'start' })}>Start work</Button>}
          {status === 'waiting' && <Button icon={<PlayCircle size={15} />} disabled={work.isPending} onClick={() => send({ action: 'resume' })}>Resume</Button>}
          <Button variant={status === 'in_progress' ? 'primary' : 'secondary'} icon={<CircleCheck size={15} />} onClick={() => setMode('resolve')}>Mark done…</Button>
          {status !== 'waiting' && <Button variant="secondary" icon={<Hourglass size={14} />} onClick={() => setMode('wait')}>Waiting for info…</Button>}
        </>
      )}
      <span className="ml-auto text-xs text-muted">Working as <b className="text-ink">{user?.name ?? '–'}</b></span>
      <div className="w-full"><ErrorBox error={work.error} /></div>
    </div>
  )
}

const ACTIVITY_LABEL: Record<string, string> = {
  triaged: 'AI triaged it', approved: 'approved and dispatched', edited: 'edited and dispatched', rejected: 'rejected the proposal',
  assigned: 'assigned it to', start: 'started work', wait: 'is waiting for information', resume: 'resumed work', resolve: 'marked it done',
}

function ActivityCard({ ticket }: { ticket: TicketDetail }) {
  return (
    <Card title="Activity" icon={<History size={15} />}>
      <ol className="relative flex flex-col gap-3 border-l border-line pl-4 text-sm">
        {ticket.activity.map((a, i) => (
          <li key={i} className="relative">
            <span className={`absolute top-1.5 -left-[21px] h-2.5 w-2.5 rounded-full ring-2 ring-surface ${a.action === 'resolve' ? 'bg-emerald-500' : a.action === 'rejected' ? 'bg-red-500' : a.action === 'triaged' ? 'bg-ai' : 'bg-slate-400'}`} />
            {a.action === 'triaged' ? <b>AI</b> : <b>{short(a.by)}</b>} {ACTIVITY_LABEL[a.action] ?? a.action}
            {a.note && <span className="text-muted"> {a.action === 'assigned' || a.action === 'approved' || a.action === 'edited' ? short(a.note) : `· ${a.note}`}</span>}
            <p className="text-xs text-muted">{new Date(a.at).toLocaleString()}</p>
          </li>
        ))}
      </ol>
    </Card>
  )
}

function Section({ title, icon, actions, children }: { title: string; icon: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-[13px] font-semibold tracking-wide text-muted uppercase">{icon}{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  )
}

export default function TicketPage() {
  const { ticketId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const { data: ticket, isLoading, error } = useTicket(ticketId)
  const { data: reference } = useReference()
  const { data: settings } = useSettings()
  const { data: models } = useLlmModels()
  const { model } = useSelectedModel()
  const stream = useTriageStream(ticketId)
  const [runModel, setRunModel] = useState<string>('')
  const [showWalkthrough, setShowWalkthrough] = useState(true)
  const [editing, setEditing] = useState(false)
  const [edits, setEdits] = useState<DecisionEdit>({})
  const [compose, setCompose] = useState<'escalate' | 'handoff' | 'question' | null>(null)
  const autoStarted = useRef(false)
  const copilot = useCopilot()
  const { user, role } = useViewer()
  const { setTicket } = copilot
  const [tid, tnum, tsum] = [ticket?.id, ticket?.number, ticket?.summary]

  // Give the Copilot this ticket as context while it's on screen.
  useEffect(() => {
    if (!tid || tnum === undefined || tsum === undefined) return
    setTicket({ id: tid, number: tnum, summary: tsum })
    return () => setTicket(null)
  }, [tid, tnum, tsum, setTicket])

  const run = () => {
    setShowWalkthrough(true)
    stream.start(runModel || model)
  }

  useEffect(() => {
    if (params.get('run') === '1' && ticket && !autoStarted.current) {
      autoStarted.current = true
      setParams({}, { replace: true })
      stream.start(runModel || model)
    }
  }, [params, ticket, setParams, stream, runModel, model])

  if (isLoading) return <Loading />
  if (error || !ticket) return <ErrorBox error={error ?? new Error('Ticket not found')} />
  const result = ticket.latest_triage
  const setEdit = <K extends keyof DecisionEdit>(key: K, value: DecisionEdit[K]) => setEdits((e) => ({ ...e, [key]: value }))
  const hasWalkthrough = stream.events.length > 0 || stream.running

  return (
    <div className="flex flex-col gap-5">
      {/* header */}
      <div className="rounded-xl border border-line bg-surface p-5 shadow-card">
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted hover:text-accent"><ArrowLeft size={14} />Queue</Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="font-mono text-xs text-muted">#{ticket.number} · {ticket.source} · {ticket.business_entity ?? 'no entity'} · {ticket.reporter ?? 'unknown reporter'}</p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight text-balance">{ticket.summary}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {result && <><PriorityPill level={ticket.ai_priority} /><ScoreBar score={ticket.priority_score} /></>}
              {result && <SlaTimer dueAt={ticket.sla_due_at} startAt={ticket.created_at} closed={ticket.work_status === 'done'} />}
              <WorkStatusPill ticket={ticket} />
              {ticket.work_status !== 'open' && ticket.assignee && <span className="text-xs text-muted">with <b className="text-ink">{short(ticket.assignee)}</b></span>}
              {ticket.escalated && <Pill className="bg-red-50 text-red-700 ring-1 ring-red-200">escalated to the team lead</Pill>}
              {ticket.manual_fields.length > 0 && <Pill className="bg-accent-soft text-accent">{ticket.manual_fields.length} fields set by staff</Pill>}
            </div>
          </div>
          {(canDispatch(role) || !result) && <div className="flex flex-wrap items-center gap-2">
            <label className="sr-only" htmlFor="run-model">Model</label>
            <select id="run-model" value={runModel} onChange={(e) => setRunModel(e.target.value)} className="rounded-lg border border-line bg-surface px-2 py-1.5 text-sm">
              <option value="">{model ? `Model: ${model}` : 'Default model'}</option>
              {models?.models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
              <option value={HEURISTIC}>Heuristic (no LLM)</option>
            </select>
            <Button variant="ai" icon={<Play size={14} />} onClick={run} disabled={stream.running}>
              {stream.running ? 'Triaging…' : result ? 'Re-run live' : 'Watch the AI triage it'}
            </Button>
          </div>}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-3">
          <Button variant="secondary" className="text-red-600" icon={<Siren size={14} />} onClick={() => setCompose('escalate')} disabled={!result}>Escalate</Button>
          <Button variant="secondary" icon={<MessagesSquare size={14} />} onClick={() => setCompose('handoff')} disabled={!result}>Message about this ticket</Button>
          <Button variant="ghost" icon={<Sparkles size={14} />} onClick={() => copilot.ask(`Summarise ticket #${ticket.number} and suggest the next step.`)}>Ask Copilot</Button>
          {!result && <span className="text-xs text-muted">Triage first to escalate or hand off with full context.</span>}
        </div>
      </div>

      {/* live walkthrough */}
      {hasWalkthrough && (
        <Section title="Live triage walkthrough" icon={<Sparkles size={14} />}
          actions={<Button variant="ghost" className="text-xs" icon={showWalkthrough ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            onClick={() => setShowWalkthrough((v) => !v)}>{showWalkthrough ? 'Hide' : 'Show'}</Button>}>
          {showWalkthrough && <Walkthrough events={stream.events} running={stream.running} reference={reference} votesTotal={settings?.votes ?? 3} />}
          {stream.error && <ErrorBox error={new Error(stream.error)} />}
        </Section>
      )}

      {!result && !hasWalkthrough && (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-ai/40 bg-ai-soft/40 px-6 py-10 text-center">
          <Sparkles size={28} className="text-ai" />
          <p className="font-semibold">This ticket hasn't been triaged yet</p>
          <p className="max-w-lg text-sm text-muted">Watch the AI work through it step by step: find similar past cases, vote on the facts, apply the priority rules, measure its own confidence and pick the right person.</p>
          <Button variant="ai" icon={<Play size={14} />} onClick={run}>Watch the AI triage it</Button>
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[1fr_1.35fr_1fr]">
        <div className="flex flex-col gap-4">
          <Card title="As received" icon={<Inbox size={15} />}>
            <p className="mb-3 text-sm leading-relaxed whitespace-pre-wrap">{ticket.description}</p>
            <dl className="divide-y divide-line/70">
              <Field label="Request type">{ticket.request_type}</Field>
              <Field label="Work type">{ticket.work_type}</Field>
              <Field label="Intake service">{ticket.affected_service}</Field>
              <Field label="Entity">{ticket.business_entity}</Field>
              <Field label="Urgency / Impact">{ticket.urgency ?? '–'} / {ticket.impact ?? '–'}</Field>
              <Field label="Priority"><PriorityPill level={ticket.priority} /></Field>
              <Field label="Linked issues">{ticket.linked_issues.join(', ') || '–'}</Field>
            </dl>
          </Card>
          <Card title={`Comments (${ticket.comments.length})`} icon={<MessagesSquare size={15} />}>
            {ticket.comments.length === 0 ? <p className="text-sm text-muted">None.</p> : (
              <ul className="flex flex-col gap-2 text-sm">
                {ticket.comments.map((c, i) => <li key={i} className="border-l-2 border-line pl-3">{c}</li>)}
              </ul>
            )}
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          {ticket.work_status === 'done' && (
            <Card title={<>Closing note <span className="font-normal text-muted">· by {short(ticket.resolved_by)}</span></>} icon={<CircleCheck size={15} className="text-emerald-600" />}
              actions={<Pill className="bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200">in the knowledge base</Pill>}>
              <p className="mb-2 text-sm"><span className="text-muted">Resolution:</span> <b>{ticket.resolution}</b>
                {ticket.resolved_at && <span className="text-xs text-muted"> · {new Date(ticket.resolved_at).toLocaleString()}</span>}</p>
              <blockquote className="rounded-lg border-l-4 border-emerald-500 bg-emerald-50/60 p-3 text-sm leading-relaxed">{ticket.resolution_comment}</blockquote>
            </Card>
          )}
          {result ? (
            <ProposalPanels key={result.id} ticket={ticket} result={result} editing={editing} edits={edits} setEdit={setEdit} />
          ) : (
            <Card title="AI proposal" icon={<Sparkles size={15} />}><p className="text-sm text-muted">{stream.running ? 'Working on it…' : 'No proposal yet.'}</p></Card>
          )}
        </div>

        <div className="flex flex-col gap-4">
          {result && <ConfidencePanel result={result} />}
          {result && <AssigneePanel ticket={ticket} result={result} />}
          {result && (
            <Card title="Evidence used" icon={<BookOpen size={15} />}>
              <EvidenceList evidence={result.evidence} highlight={result.playbook_ref} />
            </Card>
          )}
          {ticket.activity.length > 0 && <ActivityCard ticket={ticket} />}
          {ticket.activity.length === 0 && ticket.reviews.length > 0 && (
            <Card title="Review history" icon={<History size={15} />}>
              <ul className="flex flex-col gap-2 text-sm">
                {ticket.reviews.map((r) => (
                  <li key={r.id}>
                    <StatePill state={r.action === 'approve' ? 'approved' : r.action === 'edit' ? 'edited' : 'rejected'} /> by <b>{short(r.reviewer)}</b>
                    {r.overridden_fields.length > 0 && <span className="text-muted"> · changed {r.overridden_fields.join(', ')}</span>}
                    {r.notes && <span className="text-muted">: “{r.notes}”</span>}
                    <p className="text-xs text-muted">{new Date(r.created_at).toLocaleString()}</p>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>

      {compose && <ComposeDialog ticket={ticket} initialPurpose={compose} onClose={() => setCompose(null)} />}

      {result && !stream.running && ticket.work_status === 'open' && canDispatch(role) && (
        <DecisionBar key={result.id} result={result} editing={editing} setEditing={setEditing} edits={edits} reset={() => setEdits({})} />
      )}
      {!stream.running && ['assigned', 'in_progress', 'waiting'].includes(ticket.work_status) && (user?.email === ticket.assignee || role === 'admin') && (
        <WorkBar key={`${ticket.id}-${ticket.work_status}`} ticket={ticket} result={result ?? null} />
      )}
    </div>
  )
}
