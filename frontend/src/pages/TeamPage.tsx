import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useReference, useWorkload } from '../api/hooks'
import { SlaTimer } from '../components/triage'
import { Card, ErrorBox, Loading, PageHeader, PriorityPill } from '../components/ui'
import { useViewer } from '../viewas/context'

export default function TeamPage() {
  const { user } = useViewer()
  const { data: reference } = useReference()
  const [chosen, setChosen] = useState<string>('')
  const team = chosen || user?.teams[0] || reference?.teams[0]
  const { data, isLoading, error } = useWorkload(team)

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="Team workload" subtitle="Nobody should hold more than 30% of the team's open tickets or exceed their capacity."
        actions={<>
          <label className="sr-only" htmlFor="team-select">Team</label>
          <select id="team-select" value={team ?? ''} onChange={(e) => setChosen(e.target.value)} className="rounded-lg border border-line bg-surface px-2 py-1.5 text-sm">
            {reference?.teams.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </>} />
      <ErrorBox error={error} />
      {isLoading && <Loading />}
      {data && (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-surface shadow-card">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-canvas/60 text-[11px] font-semibold tracking-wider text-muted uppercase">
                <tr><th className="px-3 py-2">Specialist</th><th className="px-3 py-2">Open / capacity</th><th className="px-3 py-2">Share of team</th><th className="px-3 py-2">High+Highest</th><th className="px-3 py-2">Oldest open</th><th className="px-3 py-2">Done (7d)</th></tr>
              </thead>
              <tbody>
                {data.members.map((m) => {
                  const load = m.capacity ? m.open / m.capacity : 0
                  const over = m.open >= m.capacity || m.share >= 0.3
                  return (
                    <tr key={m.email} className="border-t border-line">
                      <td className="px-3 py-2">{m.name}{m.role === 'analyst' && <span className="ml-1 text-xs text-muted">team lead</span>}</td>
                      <td className="px-3 py-2">
                        <span className="inline-flex items-center gap-2">
                          <span className="inline-block h-2 w-24 overflow-hidden rounded bg-slate-100">
                            <span className={`block h-2 ${load >= 1 ? 'bg-red-600' : load >= 0.6 ? 'bg-amber-500' : 'bg-emerald-600'}`} style={{ width: `${Math.min(100, load * 100)}%` }} />
                          </span>
                          <span className="tabular-nums">{m.open}/{m.capacity}</span>
                        </span>
                      </td>
                      <td className={`px-3 py-2 tabular-nums ${over ? 'font-semibold text-red-700' : ''}`}>{Math.round(m.share * 100)}%{over && ' ⚠'}</td>
                      <td className="px-3 py-2 tabular-nums">{m.high_open}</td>
                      <td className="px-3 py-2">{m.oldest_open_at ? new Date(m.oldest_open_at).toLocaleDateString() : '–'}</td>
                      <td className="px-3 py-2 tabular-nums">{m.resolved_7d}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <p className="border-t border-line px-3 py-2 text-xs text-muted">{data.open_total} open tickets in {data.team}</p>
          </div>
          <Card title={`Escalations (${data.escalations.length})`}>
            {data.escalations.length === 0 ? <p className="text-sm text-muted">No open escalations.</p> : (
              <ul className="flex flex-col gap-2 text-sm">
                {data.escalations.map((t) => (
                  <li key={t.id} className="flex flex-wrap items-center gap-2">
                    <PriorityPill level={t.ai_priority} />
                    <Link to={`/tickets/${t.id}`} className="text-blue-800 hover:underline">#{t.number} {t.summary}</Link>
                    <SlaTimer dueAt={t.sla_due_at} startAt={t.created_at} closed={t.work_status === 'done'} />
                    <span className="text-xs text-muted">{t.assignee ? t.assignee.split('@')[0] : 'unassigned'}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
