import { FilePlus2, Play, Sparkles, UserPen } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCreateTicket, useReference, useUsers } from '../api/hooks'
import type { Level, TicketCreate } from '../api/types'
import { Button, Card, ErrorBox, PageHeader, PriorityPill, inputClass } from '../components/ui'
import { useViewer } from '../viewas/context'

const ENTITIES = ['Switzerland', 'France', 'Luxembourg', 'Germany', 'Nordics']
const REQUEST_TYPES = [
  'Human Created Incident', 'Machine Created Alert', 'Email / 3rd Party Warning', 'New License',
  'Access to a Service', 'Access Removal', 'Nonsense / Unclear Input',
]

type Manual = { work_type: string; service: string; urgency: string; impact: string; assignee: string; resolution: string; resolution_comment: string }
const EMPTY_MANUAL: Manual = { work_type: '', service: '', urgency: '', impact: '', assignee: '', resolution: '', resolution_comment: '' }

function Labelled({ id, label, hint, children }: { id: string; label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm font-medium" htmlFor={id}>
      <span>{label}{hint && <span className="ml-1 font-normal text-muted">{hint}</span>}</span>
      {children}
    </label>
  )
}

export default function NewTicketPage() {
  const navigate = useNavigate()
  const { user } = useViewer()
  const { data: reference } = useReference()
  const { data: users } = useUsers()
  const create = useCreateTicket()
  const [form, setForm] = useState({ summary: '', description: '', reporter: '', business_entity: '', request_type: '' })
  const [manual, setManual] = useState<Manual>(EMPTY_MANUAL)
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))
  const setM = (key: keyof Manual) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setManual((m) => ({ ...m, [key]: e.target.value }))

  const team = reference?.services.find((s) => s.name === manual.service)?.team
  const priority = manual.urgency && manual.impact ? reference?.priority_matrix[manual.urgency as Level]?.[manual.impact as Level] : undefined
  const people = (users ?? []).filter((u) => u.role === 'specialist' && (!team || u.teams.includes(team)))
  const filled = Object.entries(manual).filter(([, v]) => v).map(([k]) => k)

  const submit = async (triageNow: boolean) => {
    const cleaned = Object.fromEntries(Object.entries(manual).filter(([, v]) => v))
    const ticket = await create.mutateAsync({
      summary: form.summary,
      description: form.description,
      reporter: form.reporter || user?.email || null,
      business_entity: form.business_entity || null,
      request_type: form.request_type || null,
      source: 'manual',
      status: 'open',
      linked_issues: [],
      comments: [],
      manual: filled.length ? (cleaned as TicketCreate['manual']) : null,
      created_by: user?.email ?? null,
    })
    navigate(`/tickets/${ticket.id}${triageNow ? '?run=1' : ''}`)
  }

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const submitter = (e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null
    submit(submitter?.value !== 'create-only')
  }

  return (
    <div className="flex max-w-6xl flex-col gap-5">
      <PageHeader title="New ticket" subtitle="Describe the problem. Fill in anything you already know; the AI completes the rest and respects your values." />
      <form className="grid gap-5 lg:grid-cols-[1.5fr_1fr]" onSubmit={onSubmit}>
        <div className="flex flex-col gap-5">
          <Card title="The ticket" icon={<FilePlus2 size={15} />}>
            <div className="flex flex-col gap-4">
              <Labelled id="nt-summary" label="Summary *">
                <input id="nt-summary" required minLength={3} value={form.summary} onChange={set('summary')} className={inputClass}
                  placeholder="e.g. NAV run stopped after tolerance breach on 4 funds" />
              </Labelled>
              <Labelled id="nt-description" label="Description *">
                <textarea id="nt-description" required minLength={3} rows={6} value={form.description} onChange={set('description')} className={inputClass}
                  placeholder="What happened, since when, who is affected, IDs, deadlines, workarounds" />
              </Labelled>
              <div className="grid gap-4 sm:grid-cols-3">
                <Labelled id="nt-reporter" label="Reporter *">
                  <input id="nt-reporter" type="email" value={form.reporter} onChange={set('reporter')} className={inputClass} placeholder={user?.email ?? 'name@intcom.com'} />
                </Labelled>
                <Labelled id="nt-entity" label="Business entity">
                  <select id="nt-entity" value={form.business_entity} onChange={set('business_entity')} className={inputClass}>
                    <option value="">Not specified</option>
                    {ENTITIES.map((e) => <option key={e}>{e}</option>)}
                  </select>
                </Labelled>
                <Labelled id="nt-type" label="Request type">
                  <select id="nt-type" value={form.request_type} onChange={set('request_type')} className={inputClass}>
                    <option value="">Not specified</option>
                    {REQUEST_TYPES.map((t) => <option key={t}>{t}</option>)}
                  </select>
                </Labelled>
              </div>
            </div>
          </Card>

          <Card title="Set details yourself (optional)" icon={<UserPen size={15} />}
            actions={filled.length > 0 && <Button type="button" variant="ghost" className="text-xs" onClick={() => setManual(EMPTY_MANUAL)}>Clear</Button>}>
            <p className="mb-4 text-sm text-muted">Anything you set here is kept exactly as you entered it and marked "set by staff". Leave a field on "Let AI decide" to have it filled in.</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <Labelled id="m-work" label="Work type">
                <select id="m-work" value={manual.work_type} onChange={setM('work_type')} className={inputClass}>
                  <option value="">Let AI decide</option>
                  {reference?.work_types.map((w) => <option key={w}>{w}</option>)}
                </select>
              </Labelled>
              <Labelled id="m-service" label="Service" hint={team ? `→ team ${team}` : undefined}>
                <select id="m-service" value={manual.service} onChange={setM('service')} className={inputClass}>
                  <option value="">Let AI decide</option>
                  {reference?.services.map((s) => <option key={s.name}>{s.name}</option>)}
                </select>
              </Labelled>
              <Labelled id="m-urgency" label="Urgency">
                <select id="m-urgency" value={manual.urgency} onChange={setM('urgency')} className={inputClass}>
                  <option value="">Let AI decide</option>
                  {reference?.levels.map((l) => <option key={l} value={l}>{l} ({reference.urgency_labels[l]})</option>)}
                </select>
              </Labelled>
              <Labelled id="m-impact" label="Impact">
                <select id="m-impact" value={manual.impact} onChange={setM('impact')} className={inputClass}>
                  <option value="">Let AI decide</option>
                  {reference?.levels.map((l) => <option key={l} value={l}>{l} ({reference.impact_labels[l]})</option>)}
                </select>
              </Labelled>
              <Labelled id="m-assignee" label="Assignee" hint={team ? `members of ${team}` : undefined}>
                <select id="m-assignee" value={manual.assignee} onChange={setM('assignee')} className={inputClass}>
                  <option value="">Let AI decide</option>
                  {people.map((u) => <option key={u.email} value={u.email}>{u.name} · {u.teams[0] ?? ''}</option>)}
                </select>
              </Labelled>
              <Labelled id="m-resolution" label="Resolution status">
                <select id="m-resolution" value={manual.resolution} onChange={setM('resolution')} className={inputClass}>
                  <option value="">Let AI decide</option>
                  {reference?.resolutions.map((r) => <option key={r}>{r}</option>)}
                </select>
              </Labelled>
              <div className="sm:col-span-2">
                <Labelled id="m-comment" label="Resolution comment">
                  <textarea id="m-comment" rows={3} value={manual.resolution_comment} onChange={setM('resolution_comment')} className={inputClass}
                    placeholder="Let AI draft it, or write your own closing note" />
                </Labelled>
              </div>
            </div>
          </Card>
        </div>

        <div className="flex flex-col gap-5">
          <Card title="What happens next" icon={<Sparkles size={15} />}>
            <ul className="flex flex-col gap-3 text-sm">
              {[
                ['Work type', manual.work_type],
                ['Service', manual.service],
                ['Team', team ? `${team} (from service)` : ''],
                ['Urgency', manual.urgency],
                ['Impact', manual.impact],
                ['Priority', priority ? `${priority} (matrix)` : ''],
                ['Assignee', manual.assignee ? manual.assignee.split('@')[0] : ''],
                ['Resolution', manual.resolution],
                ['Resolution comment', manual.resolution_comment ? 'your text' : ''],
              ].map(([label, value]) => (
                <li key={label} className="flex items-center justify-between gap-2">
                  <span className="text-muted">{label}</span>
                  {value ? (
                    <span className="font-medium">{label === 'Priority' && priority ? <PriorityPill level={priority} /> : value}</span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-ai"><Sparkles size={12} />AI fills in</span>
                  )}
                </li>
              ))}
            </ul>
          </Card>
          <div className="sticky top-20 flex flex-col gap-2">
            <Button type="submit" value="create-and-triage" variant="ai" icon={<Play size={14} />} disabled={create.isPending}>
              {create.isPending ? 'Creating…' : 'Create and watch AI triage'}
            </Button>
            <Button type="submit" value="create-only" variant="secondary" disabled={create.isPending}>Create only (triage later)</Button>
            <ErrorBox error={create.error} />
          </div>
        </div>
      </form>
    </div>
  )
}
