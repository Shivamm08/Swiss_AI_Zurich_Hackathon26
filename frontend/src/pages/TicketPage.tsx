import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  useAssignTicket,
  useLlmModels,
  useReference,
  useReviewTriage,
  useTicket,
  useTriageTicket,
} from '../api/hooks'
import type { DecisionEdit, Level, ReviewCreate, TicketDetail, TriageResult } from '../api/types'
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
import { Button, Card, ErrorBox, Field, Loading, PriorityPill, StatePill } from '../components/ui'
import { HEURISTIC, useSelectedModel } from '../model/context'
import { useViewer } from '../viewas/context'

const short = (email?: string | null) => (email ? email.split('@')[0] : '–')

function ConfidencePanel({ result }: { result: TriageResult }) {
  const d = result.confidence_detail
  return (
    <Card title={`Confidence ${Math.round(result.confidence * 100)}%`} actions={<RoutePill route={result.route} />}>
      {d ? (
        <dl className="flex flex-col gap-1 text-sm">
          <div className="flex items-center justify-between"><dt className="text-slate-500">Votes agree</dt><dd><ConfidenceMeter value={d.votes} /></dd></div>
          <div className="flex items-center justify-between"><dt className="text-slate-500">Similar past case</dt><dd><ConfidenceMeter value={d.retrieval} /></dd></div>
          <div className="flex items-center justify-between"><dt className="text-slate-500">Flags</dt><dd className="text-xs">{d.flags.length ? d.flags.join(', ').replaceAll('_', ' ') : 'none'}</dd></div>
          <p className="mt-1 text-xs text-slate-500">
            {result.confidence < 0.8 &&
              `Weakest part: ${d.flags.includes('heuristic_fallback') ? 'no LLM result' : d.votes < d.retrieval ? 'the votes disagree' : 'no close past case'}.`}
          </p>
        </dl>
      ) : (
        <ConfidenceMeter value={result.confidence} />
      )}
    </Card>
  )
}

function AssigneePanel({ ticket, result }: { ticket: TicketDetail; result: TriageResult }) {
  const assign = useAssignTicket()
  const s = result.assignee_suggestion
  return (
    <Card title="Assignee">
      <dl className="flex flex-col gap-1 text-sm">
        <Field label="Working on it">{ticket.assignee ? <b>{short(ticket.assignee)}</b> : <span className="text-red-700">unassigned</span>}</Field>
        <Field label="Expert">{short(s?.expert)} <span className="text-xs text-slate-500">(used in the export)</span></Field>
        <Field label="Recommended">{short(s?.recommended)}</Field>
      </dl>
      {s && <p className="mt-1 text-xs text-slate-500">{s.reason}</p>}
      {s && s.candidates.length > 0 && (
        <table className="mt-2 w-full text-xs">
          <thead className="text-slate-500"><tr><th className="text-left">Team member</th><th>Open</th><th>Score</th><th></th></tr></thead>
          <tbody>
            {s.candidates.map((c) => (
              <tr key={c.user} className="border-t border-slate-100">
                <td className="py-1">{c.name}{c.user === s.expert && <span className="ml-1 text-blue-700">expert</span>}</td>
                <td className={`text-center tabular-nums ${c.open >= c.capacity ? 'font-semibold text-red-700' : ''}`}>{c.open}/{c.capacity}</td>
                <td className="text-center tabular-nums">{c.score.toFixed(2)}</td>
                <td className="text-right">
                  {ticket.assignee !== c.user && (
                    <button type="button" className="text-blue-700 hover:underline" disabled={assign.isPending}
                      onClick={() => assign.mutate({ ticketId: ticket.id, assignee: c.user })}>assign</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <ErrorBox error={assign.error} />
    </Card>
  )
}

function ProposalPanel({ ticket, result, editing, edits, setEdit }: {
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

  const select = (key: 'work_type' | 'service' | 'urgency' | 'impact' | 'resolution', options: readonly string[]) => (
    <select id={`edit-${key}`} aria-label={key} value={String(current[key])} onChange={(e) => setEdit(key, e.target.value as never)}
      className="rounded-md border border-slate-300 px-1.5 py-0.5 text-sm">
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  )
  const voteNote = (field: string) =>
    votes[field] !== undefined && votes[field] < 1 ? <span className="ml-1 text-xs text-amber-700">votes {Math.round(votes[field] * 100)}%</span> : null

  return (
    <>
      <Card title={`AI proposal · ${result.model}`} actions={<span className="text-xs text-slate-500">{result.latency_ms} ms</span>}>
        <dl>
          <Field label="Work type">{editing && ref ? select('work_type', ref.work_types) : <FieldDiff intake={ticket.work_type} value={current.work_type} />}{voteNote('work_type')}</Field>
          <Field label="Service">{editing && ref ? select('service', ref.services.map((s) => s.name)) : <FieldDiff intake={ticket.affected_service} value={current.service} />}{voteNote('service')}</Field>
          <Field label="Team">{team} <span className="text-xs text-slate-500">(fixed by service)</span></Field>
          <Field label="Impact">{editing && ref ? select('impact', ref.levels) : <FieldDiff intake={ticket.impact} value={current.impact} />}</Field>
          <Field label="Urgency">{editing && ref ? select('urgency', ref.levels) : <FieldDiff intake={ticket.urgency} value={current.urgency} />}</Field>
          <Field label="Priority"><PriorityPill level={priority} /><ScoreBar score={result.priority_score} />{priority !== ticket.priority && ticket.priority && <span className="ml-2 text-xs text-slate-500">was {ticket.priority}</span>}</Field>
          <Field label="Resolution">{editing && ref ? select('resolution', ref.resolutions) : current.resolution}{voteNote('resolution')}</Field>
        </dl>
        <div className="mt-3"><FactChips facts={result.facts} /></div>
        <p className="mt-2 text-xs text-slate-500">{result.rationale}</p>
      </Card>

      <Card title="Why this priority">
        <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
          <ul className="flex flex-col gap-1 text-sm">
            {(editing ? [`Priority ${priority} = matrix[urgency ${urgency}][impact ${impact}] (edited)`] : result.rubric_trace).map((line) => (
              <li key={line}>• {line}</li>
            ))}
          </ul>
          <MatrixGrid reference={ref} urgency={urgency} impact={impact} />
        </div>
      </Card>

      <Card title="Resolution draft">
        {editing ? (
          <>
            <label className="sr-only" htmlFor="edit-comment">Resolution comment</label>
            <textarea id="edit-comment" rows={5} value={current.resolution_comment} onChange={(e) => setEdit('resolution_comment', e.target.value)}
              className="w-full rounded-md border border-slate-300 p-2 text-sm" />
          </>
        ) : (
          <p className="rounded-md bg-slate-50 p-3 text-sm">{current.resolution_comment}</p>
        )}
      </Card>
    </>
  )
}

function ActionBar({ result, editing, setEditing, edits, reset }: {
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
    <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center gap-2 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:-mx-6 md:px-6">
      {rejecting ? (
        <>
          <label className="sr-only" htmlFor="reject-reason">Reason</label>
          <input id="reject-reason" autoFocus value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why is the proposal wrong?"
            className="min-w-0 flex-1 rounded-md border border-slate-300 px-2 py-1 text-sm" />
          <Button variant="danger" onClick={() => submit('reject')} disabled={review.isPending}>Reject and send to Needs review</Button>
          <Button variant="secondary" onClick={() => setRejecting(false)}>Cancel</Button>
        </>
      ) : editing ? (
        <>
          <Button onClick={() => submit('edit')} disabled={review.isPending}>Save edits</Button>
          <Button variant="secondary" onClick={() => { setEditing(false); reset() }}>Cancel</Button>
          <span className="text-xs text-slate-500">Team and priority are recomputed from service and urgency/impact.</span>
        </>
      ) : (
        <>
          <Button onClick={() => submit('approve')} disabled={review.isPending}>Approve (a)</Button>
          <Button variant="secondary" onClick={() => setEditing(true)}>Edit (e)</Button>
          <Button variant="danger" onClick={() => setRejecting(true)}>Reject (r)</Button>
        </>
      )}
      <span className="ml-auto text-xs text-slate-500">Reviewer: {user?.name ?? '–'}</span>
      <ErrorBox error={review.error} />
    </div>
  )
}

export default function TicketPage() {
  const { ticketId = '' } = useParams()
  const { data: ticket, isLoading, error } = useTicket(ticketId)
  const triage = useTriageTicket()
  const { model } = useSelectedModel()
  const { data: models } = useLlmModels()
  const [rerunModel, setRerunModel] = useState<string>('')
  const [editing, setEditing] = useState(false)
  const [edits, setEdits] = useState<DecisionEdit>({})

  if (isLoading) return <Loading />
  if (error || !ticket) return <ErrorBox error={error ?? new Error('Ticket not found')} />
  const result = ticket.latest_triage
  const setEdit = <K extends keyof DecisionEdit>(key: K, value: DecisionEdit[K]) => setEdits((e) => ({ ...e, [key]: value }))
  const runModel = rerunModel || model

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/" className="text-sm text-blue-700 hover:underline">← Queue</Link>
          <p className="font-mono text-xs text-slate-500">#{ticket.number} · {ticket.source} · {ticket.business_entity ?? 'no entity'}</p>
          <h1 className="text-xl font-semibold text-balance">{ticket.summary}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {result && <><PriorityPill level={ticket.ai_priority} /><ScoreBar score={ticket.priority_score} /></>}
          {result && <SlaTimer dueAt={ticket.sla_due_at} startAt={ticket.created_at} />}
          <StatePill state={ticket.triage_state} />
          <label className="sr-only" htmlFor="rerun-model">Model for re-run</label>
          <select id="rerun-model" value={rerunModel} onChange={(e) => setRerunModel(e.target.value)} className="rounded-md border border-slate-300 px-2 py-1 text-sm">
            <option value="">{model ? `Model: ${model}` : 'Default model'}</option>
            {models?.models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            <option value={HEURISTIC}>Heuristic (no LLM)</option>
          </select>
          <Button onClick={() => triage.mutate({ ticketId: ticket.id, model: runModel })} disabled={triage.isPending}>
            {triage.isPending ? 'Running…' : result ? 'Re-run triage' : 'Run triage'}
          </Button>
        </div>
      </header>
      <ErrorBox error={triage.error} />
      {ticket.escalated && <p className="rounded-md bg-red-50 p-3 text-sm font-medium text-red-800">Escalated to the team lead: Highest priority on a critical service.</p>}
      {result?.confidence_detail?.flags.includes('heuristic_fallback') && (
        <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-800">Heuristic fallback: {result.rationale}</p>
      )}

      <div className="grid gap-4 xl:grid-cols-[1fr_1.35fr_1fr]">
        <div className="flex flex-col gap-4">
          <Card title="As received">
            <p className="mb-3 text-sm whitespace-pre-wrap">{ticket.description}</p>
            <dl>
              <Field label="Request type">{ticket.request_type}</Field>
              <Field label="Work type">{ticket.work_type}</Field>
              <Field label="Intake service">{ticket.affected_service}</Field>
              <Field label="Entity">{ticket.business_entity}</Field>
              <Field label="Reporter">{ticket.reporter}</Field>
              <Field label="Urgency / Impact">{ticket.urgency ?? '–'} / {ticket.impact ?? '–'}</Field>
              <Field label="Priority"><PriorityPill level={ticket.priority} /></Field>
              <Field label="Linked issues">{ticket.linked_issues.join(', ') || '–'}</Field>
            </dl>
          </Card>
          <Card title={`Comments (${ticket.comments.length})`}>
            {ticket.comments.length === 0 ? <p className="text-sm text-slate-500">None.</p> : (
              <ul className="flex flex-col gap-2 text-sm">
                {ticket.comments.map((c, i) => <li key={i} className="border-l-2 border-slate-200 pl-2">{c}</li>)}
              </ul>
            )}
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          {result ? (
            <ProposalPanel key={result.id} ticket={ticket} result={result} editing={editing} edits={edits} setEdit={setEdit} />
          ) : (
            <Card title="AI proposal"><p className="text-sm text-slate-500">Not triaged yet. Run triage to get a proposal.</p></Card>
          )}
        </div>

        <div className="flex flex-col gap-4">
          {result && <ConfidencePanel result={result} />}
          {result && <AssigneePanel ticket={ticket} result={result} />}
          {result && (
            <Card title="Evidence used">
              <EvidenceList evidence={result.evidence} highlight={result.playbook_ref} />
            </Card>
          )}
          {ticket.reviews.length > 0 && (
            <Card title="Review history">
              <ul className="flex flex-col gap-1 text-sm">
                {ticket.reviews.map((r) => (
                  <li key={r.id}>
                    <b>{r.action}</b> by {short(r.reviewer)}
                    {r.overridden_fields.length > 0 && ` (changed ${r.overridden_fields.join(', ')})`}
                    {r.notes && <span className="text-slate-600">: “{r.notes}”</span>}
                    <span className="text-slate-500"> · {new Date(r.created_at).toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <Link to={`/assistant?ticket=${ticket.id}`} className="text-sm text-blue-700 hover:underline">Ask the assistant about this ticket →</Link>
        </div>
      </div>

      {result && (
        <ActionBar key={result.id} result={result} editing={editing} setEditing={setEditing} edits={edits} reset={() => setEdits({})} />
      )}
    </div>
  )
}
