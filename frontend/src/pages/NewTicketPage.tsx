import { FilePlus2, Play, Sparkles, UserPen } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCreateTicket, useReference, useUsers } from '../api/hooks'
import type { Level, TicketCreate } from '../api/types'
import type { FieldKey } from '../components/fields'
import { MethodLegend, MethodTag } from '../components/triage'
import { Button, Card, ErrorBox, PageHeader, PriorityPill, inputClass } from '../components/ui'
import { useViewer } from '../viewas/context'

const ENTITIES = ['Switzerland', 'France', 'Luxembourg', 'Germany', 'Nordics']
const REQUEST_TYPES = [
  'Human Created Incident', 'Machine Created Alert', 'Email / 3rd Party Warning', 'New License',
  'Access to a Service', 'Access Removal', 'Nonsense / Unclear Input',
]

type Manual = { work_type: string; service: string; urgency: string; impact: string; assignee: string; resolution: string; resolution_comment: string }
const EMPTY_MANUAL: Manual = { work_type: '', service: '', urgency: '', impact: '', assignee: '', resolution: '', resolution_comment: '' }

function Labelled({ id, label, hint, field, children }: { id: string; label: string; hint?: string; field?: FieldKey; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm font-medium" htmlFor={id}>
      <span className="inline-flex flex-wrap items-center gap-1">{label}{field && <MethodTag field={field} compact />}{hint && <span className="font-normal text-muted">{hint}</span>}</span>
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
      <PageHeader title="New ticket" subtitle="Describe the problem and set anything you already know. The rest is filled automatically: the AI only reads the text, and rules compute priority, team and the suggested specialist." />
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
            <p className="mb-2 text-sm text-muted">Leave a field on <b>Automatic</b> to have it filled: <b>AI reads</b> fields come from the ticket text (3 votes, fixed options only); <b>Rule</b> fields are computed, never guessed.</p>
            <p className="mb-4 text-sm text-muted">Anything you set is kept and marked "set by staff", <b>and double-checked</b>: the AI still reads the ticket without seeing your values, and the rules still compute theirs. If they disagree, the analyst sees a warning before dispatching.</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <Labelled id="m-work" label="Work type" field="work_type">
                <select id="m-work" value={manual.work_type} onChange={setM('work_type')} className={inputClass}>
                  <option value="">Automatic · AI reads it</option>
                  {reference?.work_types.map((w) => <option key={w}>{w}</option>)}
                </select>
              </Labelled>
              <Labelled id="m-service" label="Service" field="service" hint={team ? `→ team ${team}` : undefined}>
                <select id="m-service" value={manual.service} onChange={setM('service')} className={inputClass}>
                  <option value="">Automatic · AI reads it</option>
                  {reference?.services.map((s) => <option key={s.name}>{s.name}</option>)}
                </select>
              </Labelled>
              <Labelled id="m-urgency" label="Urgency" field="urgency">
                <select id="m-urgency" value={manual.urgency} onChange={setM('urgency')} className={inputClass}>
                  <option value="">Automatic · rules compute it</option>
                  {reference?.levels.map((l) => <option key={l} value={l}>{l} ({reference.urgency_labels[l]})</option>)}
                </select>
              </Labelled>
              <Labelled id="m-impact" label="Impact" field="impact">
                <select id="m-impact" value={manual.impact} onChange={setM('impact')} className={inputClass}>
                  <option value="">Automatic · rules compute it</option>
                  {reference?.levels.map((l) => <option key={l} value={l}>{l} ({reference.impact_labels[l]})</option>)}
                </select>
              </Labelled>
              <Labelled id="m-assignee" label="Specialist" field="assignee" hint={team ? `specialists of ${team}` : undefined}>
                <select id="m-assignee" value={manual.assignee} onChange={setM('assignee')} className={inputClass}>
                  <option value="">Automatic · rules suggest one</option>
                  {people.map((u) => <option key={u.email} value={u.email}>{u.name} · {u.teams[0] ?? ''}</option>)}
                </select>
              </Labelled>
              <Labelled id="m-resolution" label="Resolution status" field="resolution">
                <select id="m-resolution" value={manual.resolution} onChange={setM('resolution')} className={inputClass}>
                  <option value="">Automatic · AI reads it</option>
                  {reference?.resolutions.map((r) => <option key={r}>{r}</option>)}
                </select>
              </Labelled>
              <div className="sm:col-span-2">
                <Labelled id="m-comment" label="Resolution comment" field="resolution_comment">
                  <textarea id="m-comment" rows={3} value={manual.resolution_comment} onChange={setM('resolution_comment')} className={inputClass}
                    placeholder="Leave empty: a suggestion is drafted from the matched past fix. The specialist writes the real closing note." />
                </Labelled>
              </div>
            </div>
          </Card>
        </div>

        <div className="flex flex-col gap-5">
          <Card title="How each field is filled" icon={<Sparkles size={15} />}>
            <p className="mb-3"><MethodLegend /></p>
            <ul className="flex flex-col gap-3 text-sm">
              {([
                ['Work type', 'work_type', manual.work_type],
                ['Service', 'service', manual.service],
                ['Team', 'team', team ? `${team} (from service)` : ''],
                ['Urgency', 'urgency', manual.urgency],
                ['Impact', 'impact', manual.impact],
                ['Priority', 'priority', priority ? `${priority} (matrix)` : ''],
                ['Specialist', 'assignee', manual.assignee ? manual.assignee.split('@')[0] : ''],
                ['Resolution', 'resolution', manual.resolution],
                ['Resolution comment', 'resolution_comment', manual.resolution_comment ? 'your text' : ''],
              ] as [string, FieldKey, string][]).map(([label, field, value]) => (
                <li key={label} className="flex items-center justify-between gap-2">
                  <span className="text-muted">{label}</span>
                  {value ? (
                    <span className="font-medium">{label === 'Priority' && priority ? <PriorityPill level={priority} /> : value}
                      {(label === 'Team' || label === 'Priority') ? null : <span className="ml-1.5 text-[10px] font-semibold text-accent uppercase">staff · checked</span>}</span>
                  ) : <MethodTag field={field} align="right" />}
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
