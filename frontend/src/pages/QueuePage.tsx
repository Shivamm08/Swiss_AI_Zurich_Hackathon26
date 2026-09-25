import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useBatchTriage, useReference, useTickets } from '../api/hooks'
import type { TicketListParams, TicketView } from '../api/types'
import { ConfidenceMeter, FieldDiff, RoutePill, ScoreBar, SlaTimer } from '../components/triage'
import { Button, ErrorBox, Loading, PriorityPill, StatePill } from '../components/ui'
import { useSelectedModel } from '../model/context'
import { canLead, useViewer } from '../viewas/context'

type Sort = NonNullable<TicketListParams['sort']>

const TABS: { view: TicketView; label: string; lead?: boolean }[] = [
  { view: 'mine', label: 'My queue' },
  { view: 'team', label: 'Team' },
  { view: 'needs_review', label: 'Needs review', lead: true },
  { view: 'escalations', label: 'Escalations', lead: true },
  { view: 'all', label: 'All' },
]

function TabCount({ view, asUser }: { view: TicketView; asUser?: string }) {
  const { data } = useTickets({ view, as_user: asUser, limit: 1 })
  return <span className="ml-1 tabular-nums opacity-70">{data?.total ?? ''}</span>
}

export default function QueuePage() {
  const { user, role } = useViewer()
  const { model } = useSelectedModel()
  const navigate = useNavigate()
  const { data: reference } = useReference()
  const [view, setView] = useState<TicketView>(role === 'analyst' ? 'mine' : 'all')
  const [sort, setSort] = useState<Sort>('priority_score')
  const [service, setService] = useState('')
  const [q, setQ] = useState('')
  const params: TicketListParams = {
    view,
    as_user: user?.email,
    sort: view === 'needs_review' ? 'confidence' : sort,
    service: service || undefined,
    q: q || undefined,
    limit: 200,
  }
  const { data, isLoading, error } = useTickets(params)
  const { data: newTickets } = useTickets({ state: 'new', limit: 1 })
  const batch = useBatchTriage()

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Queue</h1>
          <p className="text-sm text-slate-500">Sorted by AI-assessed priority, then time left before the SLA deadline.</p>
        </div>
        <div className="flex gap-2">
          {role === 'admin' && <Button variant="secondary" onClick={() => navigate('/new')}>New ticket</Button>}
          <Button onClick={() => batch.mutate({ model })} disabled={batch.isPending || !newTickets?.total}>
            {batch.isPending ? 'Triaging…' : `Triage ${newTickets?.total ?? 0} new`}
          </Button>
        </div>
      </header>
      {batch.data && (
        <p className="text-sm text-slate-600">Triaged {batch.data.triaged}{batch.data.failed ? `, ${batch.data.failed} failed` : ''}.</p>
      )}
      <ErrorBox error={error ?? batch.error} />

      <div className="flex flex-wrap items-center gap-2">
        {TABS.filter((t) => !t.lead || canLead(role)).map((t) => (
          <button
            key={t.view}
            type="button"
            onClick={() => setView(t.view)}
            className={`rounded-md border px-3 py-1 text-sm ${view === t.view ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300 bg-white hover:bg-slate-50'}`}
          >
            {t.label}
            <TabCount view={t.view} asUser={user?.email} />
          </button>
        ))}
        <div className="ml-auto flex flex-wrap gap-2">
          <label className="sr-only" htmlFor="queue-search">Search</label>
          <input id="queue-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…"
            className="w-44 rounded-md border border-slate-300 px-2 py-1 text-sm" />
          <label className="sr-only" htmlFor="queue-service">Service</label>
          <select id="queue-service" value={service} onChange={(e) => setService(e.target.value)} className="rounded-md border border-slate-300 px-2 py-1 text-sm">
            <option value="">All services</option>
            {reference?.services.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
          <label className="sr-only" htmlFor="queue-sort">Sort</label>
          <select id="queue-sort" value={sort} onChange={(e) => setSort(e.target.value as Sort)} className="rounded-md border border-slate-300 px-2 py-1 text-sm">
            <option value="priority_score">Priority</option>
            <option value="sla_due_at">SLA deadline</option>
            <option value="confidence">Least confident</option>
            <option value="number">Newest</option>
          </select>
        </div>
      </div>

      {isLoading && <Loading />}
      {data && data.items.length === 0 && (
        <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
          {view === 'mine' ? 'Nothing assigned to you. Nice.' : 'No tickets here.'}
        </p>
      )}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
              <tr>
                <th className="px-3 py-2">Priority</th>
                <th className="px-3 py-2">SLA</th>
                <th className="px-3 py-2">#</th>
                <th className="px-3 py-2">Summary</th>
                <th className="px-3 py-2">Service (AI)</th>
                <th className="px-3 py-2">Assignee</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">State</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((t) => (
                <tr key={t.id} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50" onClick={() => navigate(`/tickets/${t.id}`)}>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <PriorityPill level={t.ai_priority ?? t.priority} />
                    <ScoreBar score={t.priority_score} />
                  </td>
                  <td className="px-3 py-2"><SlaTimer dueAt={t.sla_due_at} startAt={t.created_at} /></td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">{t.number}</td>
                  <td className="max-w-md px-3 py-2">
                    <Link to={`/tickets/${t.id}`} className="text-blue-800 hover:underline" onClick={(e) => e.stopPropagation()}>{t.summary}</Link>
                    {t.escalated && <span className="ml-2 text-xs font-semibold text-red-700">escalated</span>}
                  </td>
                  <td className="px-3 py-2"><FieldDiff intake={t.affected_service} value={t.ai_service} /></td>
                  <td className="px-3 py-2 text-xs">{t.assignee ? (t.assignee === user?.email ? 'you' : t.assignee.split('@')[0]) : '–'}</td>
                  <td className="px-3 py-2"><ConfidenceMeter value={t.confidence} /></td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {t.triage_state === 'proposed' && t.route ? <RoutePill route={t.route} /> : <StatePill state={t.triage_state} />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500">{data.total} tickets</p>
        </div>
      )}
    </div>
  )
}
