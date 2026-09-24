import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useReference, useReviewTriage, useTicket, useTriageTicket } from '../api/hooks'
import type { DecisionEdit, Level, ReviewCreate, TriageResult } from '../api/types'
import { Button, Card, ErrorBox, Field, Loading, PriorityPill, StatePill } from '../components/ui'
import { useSelectedModel } from '../model/context'

function reviewerName() {
  try {
    return localStorage.getItem('reviewer') ?? ''
  } catch {
    return ''
  }
}

function ReviewPanel({ result, ticketId }: { result: TriageResult; ticketId: string }) {
  const { data: ref } = useReference()
  const review = useReviewTriage()
  const [openedAt] = useState(() => Date.now()) // for review_seconds
  const [reviewer, setReviewer] = useState(reviewerName)
  const [editing, setEditing] = useState(false)
  const [edits, setEdits] = useState<DecisionEdit>({})

  const current = { ...result, ...edits }
  // Preview uses the same matrix/team map as the backend, served by /api/reference.
  const previewPriority = ref?.priority_matrix[current.urgency as Level]?.[current.impact as Level]
  const previewTeam = ref?.services.find((s) => s.name === current.service)?.team

  const submit = (action: ReviewCreate['action']) => {
    try {
      localStorage.setItem('reviewer', reviewer)
    } catch {
      /* storage unavailable */
    }
    review.mutate(
      {
        resultId: result.id,
        body: {
          action,
          edits: action === 'edit' ? edits : null,
          reviewer: reviewer || 'analyst',
          review_seconds: (Date.now() - openedAt) / 1000,
        },
      },
      { onSuccess: () => setEditing(false) },
    )
  }

  const set = <K extends keyof DecisionEdit>(key: K, value: DecisionEdit[K]) => setEdits((e) => ({ ...e, [key]: value }))

  return (
    <Card title="Analyst review">
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm" htmlFor={`reviewer-${ticketId}`}>
          Your name
          <input
            id={`reviewer-${ticketId}`}
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1"
          />
        </label>

        {editing && ref && (
          <div className="grid gap-2 sm:grid-cols-2">
            {(
              [
                ['work_type', 'Work type', ref.work_types],
                ['service', 'Service', ref.services.map((s) => s.name)],
                ['urgency', 'Urgency', ref.levels],
                ['impact', 'Impact', ref.levels],
                ['resolution', 'Resolution', ref.resolutions],
              ] as const
            ).map(([key, label, options]) => (
              <label key={key} className="flex flex-col gap-1 text-sm" htmlFor={`edit-${key}`}>
                {label}
                <select
                  id={`edit-${key}`}
                  value={String(current[key])}
                  onChange={(e) => set(key, e.target.value as never)}
                  className="rounded-md border border-slate-300 px-2 py-1"
                >
                  {options.map((o) => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
              </label>
            ))}
            <label className="flex flex-col gap-1 text-sm" htmlFor="edit-assignee">
              Assignee
              <input
                id="edit-assignee"
                value={current.assignee ?? ''}
                onChange={(e) => set('assignee', e.target.value)}
                className="rounded-md border border-slate-300 px-2 py-1"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm sm:col-span-2" htmlFor="edit-comment">
              Resolution comment
              <textarea
                id="edit-comment"
                rows={4}
                value={current.resolution_comment}
                onChange={(e) => set('resolution_comment', e.target.value)}
                className="rounded-md border border-slate-300 px-2 py-1"
              />
            </label>
            <p className="text-sm text-slate-600 sm:col-span-2">
              Team becomes <b>{previewTeam}</b>, priority becomes <PriorityPill level={previewPriority} /> (computed by
              the matrix).
            </p>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {editing ? (
            <>
              <Button onClick={() => submit('edit')} disabled={review.isPending}>Save edits</Button>
              <Button variant="secondary" onClick={() => { setEditing(false); setEdits({}) }}>Cancel</Button>
            </>
          ) : (
            <>
              <Button onClick={() => submit('approve')} disabled={review.isPending}>Approve</Button>
              <Button variant="secondary" onClick={() => setEditing(true)}>Edit</Button>
              <Button variant="danger" onClick={() => submit('reject')} disabled={review.isPending}>Reject</Button>
            </>
          )}
        </div>
        <ErrorBox error={review.error} />
      </div>
    </Card>
  )
}

export default function TicketPage() {
  const { ticketId = '' } = useParams()
  const { data: ticket, isLoading, error } = useTicket(ticketId)
  const triage = useTriageTicket()
  const { model } = useSelectedModel()

  if (isLoading) return <Loading />
  if (error || !ticket) return <ErrorBox error={error ?? new Error('Ticket not found')} />
  const result = ticket.latest_triage

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-mono text-xs text-slate-500">#{ticket.number} · {ticket.source}</p>
          <h1 className="text-xl font-semibold text-balance">{ticket.summary}</h1>
        </div>
        <div className="flex items-center gap-2">
          <StatePill state={ticket.triage_state} />
          <Button onClick={() => triage.mutate({ ticketId: ticket.id, model })} disabled={triage.isPending}>
            {triage.isPending ? 'Running…' : result ? 'Re-run triage' : 'Run triage'}
          </Button>
        </div>
      </header>
      <ErrorBox error={triage.error} />

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-4">
          <Card title="Ticket as received">
            <p className="mb-3 text-sm whitespace-pre-wrap">{ticket.description}</p>
            <dl>
              <Field label="Work type">{ticket.work_type}</Field>
              <Field label="Request type">{ticket.request_type}</Field>
              <Field label="Intake service">{ticket.affected_service}</Field>
              <Field label="Entity">{ticket.business_entity}</Field>
              <Field label="Reporter">{ticket.reporter}</Field>
              <Field label="Urgency / Impact">{ticket.urgency} / {ticket.impact}</Field>
              <Field label="Priority"><PriorityPill level={ticket.priority} /></Field>
              <Field label="Linked issues">{ticket.linked_issues.join(', ') || '-'}</Field>
            </dl>
          </Card>
          <Card title={`Comments (${ticket.comments.length})`}>
            <ul className="flex flex-col gap-2 text-sm">
              {ticket.comments.map((c, i) => <li key={i} className="border-l-2 border-slate-200 pl-2">{c}</li>)}
            </ul>
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          {!result ? (
            <Card title="AI proposal"><p className="text-sm text-slate-500">Not triaged yet.</p></Card>
          ) : (
            <>
              <Card
                title="AI proposal"
                actions={
                  <span className="text-xs text-slate-500">
                    {result.model} · {Math.round(result.confidence * 100)}% · {result.latency_ms} ms
                  </span>
                }
              >
                <dl>
                  {(
                    [
                      ['Work type', 'work_type'],
                      ['Service', 'service'],
                      ['Team', 'team'],
                      ['Assignee', 'assignee'],
                      ['Urgency', 'urgency'],
                      ['Impact', 'impact'],
                      ['Resolution', 'resolution'],
                    ] as const
                  ).map(([label, key]) => (
                    <Field key={key} label={label}>
                      {result[key] ?? '-'}
                      {result.changed_fields.includes(key) && (
                        <span className="ml-2 text-xs text-violet-700">changed from intake</span>
                      )}
                    </Field>
                  ))}
                  <Field label="Priority"><PriorityPill level={result.priority} /></Field>
                </dl>
                <p className="mt-3 rounded-md bg-slate-50 p-3 text-sm">{result.resolution_comment}</p>
                <p className="mt-2 text-xs text-slate-500">{result.rationale}</p>
              </Card>
              <ReviewPanel key={result.id} result={result} ticketId={ticket.id} />
              <Card title="Evidence used (retrieved knowledge)">
                <ul className="flex flex-col gap-2 text-sm">
                  {result.evidence.map((e) => (
                    <li key={e.ref_id}>
                      <span className="font-mono text-xs text-slate-500">{e.kind} · {e.score.toFixed(2)}</span>
                      <p className="font-medium">{e.title}</p>
                    </li>
                  ))}
                </ul>
              </Card>
            </>
          )}
          {ticket.reviews.length > 0 && (
            <Card title="Review history">
              <ul className="flex flex-col gap-1 text-sm">
                {ticket.reviews.map((r) => (
                  <li key={r.id}>
                    <b>{r.action}</b> by {r.reviewer}
                    {r.overridden_fields.length > 0 && ` (changed ${r.overridden_fields.join(', ')})`}
                    <span className="text-slate-500"> · {new Date(r.created_at).toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
