import { FilePlus2, Inbox, Play, Search, ShieldAlert } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useReference, useTickets } from '../api/hooks'
import type { Level, TicketListParams, TicketView } from '../api/types'
import { ConfidenceMeter, FieldDiff, RoutePill, ScoreBar, SlaTimer } from '../components/triage'
import { PRIORITY_STYLES } from '../components/styles'
import { Button, EmptyState, ErrorBox, Loading, PageHeader, PriorityPill, StatePill } from '../components/ui'
import { canLead, useViewer } from '../viewas/context'

type Sort = NonNullable<TicketListParams['sort']>

const TABS: { view: TicketView; label: string; lead?: boolean }[] = [
  { view: 'mine', label: 'My queue' },
  { view: 'team', label: 'My team' },
  { view: 'needs_review', label: 'Needs review', lead: true },
  { view: 'escalations', label: 'Escalations', lead: true },
  { view: 'all', label: 'All tickets' },
]

function TabCount({ view, asUser }: { view: TicketView; asUser?: string }) {
  const { data } = useTickets({ view, as_user: asUser, limit: 1 })
  if (data?.total === undefined) return null
  const alert = (view === 'needs_review' || view === 'escalations') && data.total > 0
  return <span className={`ml-1.5 rounded-full px-1.5 text-[11px] tabular ${alert ? 'bg-red-500 text-white' : 'bg-black/5'}`}>{data.total}</span>
}

export default function QueuePage() {
  const { user, role } = useViewer()
  const navigate = useNavigate()
  const { data: reference } = useReference()
  const [view, setView] = useState<TicketView>(role === 'analyst' ? 'mine' : 'all')
  const [sort, setSort] = useState<Sort>('priority_score')
  const [service, setService] = useState('')
  const [q, setQ] = useState('')
  const [showClosed, setShowClosed] = useState(false)
  const { data, isLoading, error } = useTickets({
    include_closed: showClosed,
    view,
    as_user: user?.email,
    sort: view === 'needs_review' ? 'confidence' : sort,
    service: service || undefined,
    q: q || undefined,
    limit: 200,
  })

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Queue"
        subtitle="Ranked by AI-assessed priority, then by time left before the SLA deadline. Open a ticket to watch the AI triage it."
        actions={canLead(role) && <Button variant="secondary" icon={<FilePlus2 size={15} />} onClick={() => navigate('/new')}>New ticket</Button>}
      />

      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-lg border border-line bg-surface p-0.5 shadow-card">
          {TABS.filter((t) => !t.lead || canLead(role)).map((t) => (
            <button key={t.view} type="button" onClick={() => setView(t.view)}
              className={`rounded-md px-3 py-1.5 text-sm transition ${view === t.view ? 'bg-ink text-white shadow-sm' : 'text-muted hover:text-ink'}`}>
              {t.label}
              <TabCount view={t.view} asUser={user?.email} />
            </button>
          ))}
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <label className="relative" htmlFor="queue-search">
            <span className="sr-only">Search</span>
            <Search size={15} className="pointer-events-none absolute top-2.5 left-2.5 text-muted" />
            <input id="queue-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search tickets"
              className="w-52 rounded-lg border border-line bg-surface py-1.5 pr-3 pl-8 text-sm focus:border-accent focus:outline-none" />
          </label>
          <label className="sr-only" htmlFor="queue-service">Service</label>
          <select id="queue-service" value={service} onChange={(e) => setService(e.target.value)}
            className="rounded-lg border border-line bg-surface px-2 py-1.5 text-sm">
            <option value="">All services</option>
            {reference?.services.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
          <label className="flex items-center gap-1.5 text-sm text-muted" htmlFor="queue-closed">
            <input id="queue-closed" type="checkbox" checked={showClosed} onChange={(e) => setShowClosed(e.target.checked)} className="accent-[var(--color-accent)]" />
            Show closed
          </label>
          <label className="sr-only" htmlFor="queue-sort">Sort</label>
          <select id="queue-sort" value={sort} onChange={(e) => setSort(e.target.value as Sort)}
            className="rounded-lg border border-line bg-surface px-2 py-1.5 text-sm">
            <option value="priority_score">Sort: priority</option>
            <option value="sla_due_at">Sort: SLA deadline</option>
            <option value="confidence">Sort: least confident</option>
            <option value="number">Sort: newest</option>
          </select>
        </div>
      </div>

      <ErrorBox error={error} />
      {isLoading && <Loading />}
      {data && data.items.length === 0 && (
        <EmptyState icon={view === 'needs_review' ? <ShieldAlert size={28} /> : <Inbox size={28} />}
          title={view === 'mine' ? 'Nothing assigned to you' : 'No tickets here'}>
          {view === 'mine' ? 'New tickets land here once the AI routes them to you.' : 'Import tickets or create one to get started.'}
        </EmptyState>
      )}
      {data && data.items.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-line bg-surface shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-canvas/60 text-[11px] font-semibold tracking-wider text-muted uppercase">
                <tr>
                  <th className="py-2.5 pr-3 pl-5">Priority</th>
                  <th className="px-3 py-2.5">SLA</th>
                  <th className="px-3 py-2.5">Ticket</th>
                  <th className="px-3 py-2.5">Service (AI)</th>
                  <th className="px-3 py-2.5">Assignee</th>
                  <th className="px-3 py-2.5">Confidence</th>
                  <th className="px-3 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.items.map((t) => {
                  const level = (t.ai_priority ?? t.priority) as Level | null
                  const untriaged = t.triage_state === 'new'
                  return (
                    <tr key={t.id} className="group cursor-pointer transition hover:bg-accent-soft/40" onClick={() => navigate(`/tickets/${t.id}`)}>
                      <td className="relative py-3 pr-3 pl-5 whitespace-nowrap">
                        <span className={`absolute inset-y-0 left-0 w-1 ${level ? PRIORITY_STYLES[level]?.stripe : 'bg-transparent'}`} />
                        <PriorityPill level={level} />
                        <ScoreBar score={t.priority_score} />
                      </td>
                      <td className="px-3 py-3"><SlaTimer dueAt={t.sla_due_at} startAt={t.created_at} closed={t.status === 'done'} /></td>
                      <td className="max-w-lg px-3 py-3">
                        <p className="font-medium text-ink group-hover:text-accent">{t.summary}</p>
                        <p className="mt-0.5 font-mono text-[11px] text-muted">
                          #{t.number} · {t.source}{t.business_entity ? ` · ${t.business_entity}` : ''}
                          {t.escalated && <span className="ml-2 font-sans font-semibold text-red-600">escalated</span>}
                        </p>
                      </td>
                      <td className="px-3 py-3"><FieldDiff intake={t.affected_service} value={t.ai_service} /></td>
                      <td className="px-3 py-3 text-xs">
                        {t.assignee ? <span className="font-medium">{t.assignee === user?.email ? 'You' : t.assignee.split('@')[0]}</span> : <span className="text-muted">–</span>}
                      </td>
                      <td className="px-3 py-3"><ConfidenceMeter value={t.confidence} /></td>
                      <td className="px-3 py-3 whitespace-nowrap">
                        {untriaged ? (
                          <Button variant="ai" className="px-2.5 py-1 text-xs" icon={<Play size={12} />}
                            onClick={(e) => { e.stopPropagation(); navigate(`/tickets/${t.id}?run=1`) }}>
                            Triage
                          </Button>
                        ) : t.triage_state === 'proposed' && t.route ? <RoutePill route={t.route} /> : <StatePill state={t.triage_state} />}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="border-t border-line px-5 py-2 text-xs text-muted">{data.total} tickets</p>
        </div>
      )}
    </div>
  )
}
