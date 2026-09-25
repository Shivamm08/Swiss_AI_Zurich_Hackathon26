import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCreateTicket, useReference, useTriageTicket } from '../api/hooks'
import { Button, Card, ErrorBox } from '../components/ui'
import { useSelectedModel } from '../model/context'
import { useViewer } from '../viewas/context'

const ENTITIES = ['Switzerland', 'France', 'Luxembourg', 'Germany', 'Nordics']
const REQUEST_TYPES = [
  'Human Created Incident', 'Machine Created Alert', 'Email / 3rd Party Warning', 'New License',
  'Access to a Service', 'Access Removal', 'Nonsense / Unclear Input',
]
const DERIVED = [
  ['Work type', 'AI reads the description (titles can lie)'],
  ['Affected service', 'AI, checked against the service catalogue'],
  ['Service team', 'fixed lookup from the service'],
  ['Impact · Urgency', 'AI extracts facts, the rubric decides'],
  ['Priority', 'the Urgency × Impact matrix'],
  ['Assignee', 'expert for this problem, balanced by workload'],
  ['Resolution + comment', 'AI draft from the closest past solution'],
  ['Status · created · SLA deadline', 'set automatically'],
]

const input = 'rounded-md border border-slate-300 px-2 py-1.5 text-sm'

export default function NewTicketPage() {
  const navigate = useNavigate()
  const { user } = useViewer()
  const { model } = useSelectedModel()
  const { data: reference } = useReference()
  const create = useCreateTicket()
  const triage = useTriageTicket()
  const [form, setForm] = useState({ summary: '', description: '', reporter: '', business_entity: '', request_type: '', affected_service: '' })
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))
  const busy = create.isPending || triage.isPending

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const ticket = await create.mutateAsync({
      summary: form.summary,
      description: form.description,
      reporter: form.reporter || user?.email || null,
      business_entity: form.business_entity || null,
      request_type: form.request_type || null,
      affected_service: form.affected_service || null,
      source: 'manual',
      status: 'open',
      linked_issues: [],
      comments: [],
    })
    await triage.mutateAsync({ ticketId: ticket.id, model })
    navigate(`/tickets/${ticket.id}`)
  }

  return (
    <div className="grid max-w-5xl gap-4 lg:grid-cols-[1.4fr_1fr]">
      <Card title="New ticket">
        <form className="flex flex-col gap-3" onSubmit={submit}>
          <p className="text-sm text-slate-600">Fill in what you know. Everything else is derived and shown for review.</p>
          <label className="flex flex-col gap-1 text-sm" htmlFor="nt-summary">Summary *
            <input id="nt-summary" required minLength={3} value={form.summary} onChange={set('summary')} className={input} placeholder="e.g. NAV run stopped after tolerance breach on 4 funds" />
          </label>
          <label className="flex flex-col gap-1 text-sm" htmlFor="nt-description">Description *
            <textarea id="nt-description" required minLength={3} rows={6} value={form.description} onChange={set('description')} className={input}
              placeholder="What happened, since when, who is affected, any IDs, deadlines or workarounds" />
          </label>
          <label className="flex flex-col gap-1 text-sm" htmlFor="nt-reporter">Reporter *
            <input id="nt-reporter" type="email" value={form.reporter} onChange={set('reporter')} className={input} placeholder={user?.email ?? 'name@intcom.com'} />
          </label>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-sm" htmlFor="nt-entity">Business entity
              <select id="nt-entity" value={form.business_entity} onChange={set('business_entity')} className={input}>
                <option value="">Let AI infer</option>
                {ENTITIES.map((e) => <option key={e}>{e}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm" htmlFor="nt-type">Request type
              <select id="nt-type" value={form.request_type} onChange={set('request_type')} className={input}>
                <option value="">Not specified</option>
                {REQUEST_TYPES.map((t) => <option key={t}>{t}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm" htmlFor="nt-service">Service (your guess)
              <select id="nt-service" value={form.affected_service} onChange={set('affected_service')} className={input}>
                <option value="">Let AI decide</option>
                {reference?.services.map((s) => <option key={s.name}>{s.name}</option>)}
              </select>
            </label>
          </div>
          <div className="flex items-center gap-2">
            <Button type="submit" disabled={busy}>{create.isPending ? 'Creating…' : triage.isPending ? 'Triaging…' : 'Create and triage'}</Button>
            <span className="text-xs text-slate-500">Uses model: {model ?? 'default'}</span>
          </div>
          <ErrorBox error={create.error ?? triage.error} />
        </form>
      </Card>
      <Card title="Filled in automatically">
        <dl className="flex flex-col gap-2 text-sm">
          {DERIVED.map(([field, how]) => (
            <div key={field}><dt className="font-medium">{field}</dt><dd className="text-slate-500">{how}</dd></div>
          ))}
        </dl>
      </Card>
    </div>
  )
}
