import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTickets } from '../api/hooks'
import type { TriageState } from '../api/types'
import { ErrorBox, Loading, PriorityPill, StatePill } from '../components/ui'

const STATES: TriageState[] = ['new', 'proposed', 'approved', 'edited', 'rejected']

export default function TicketsPage() {
  const [state, setState] = useState<TriageState | ''>('')
  const [q, setQ] = useState('')
  const { data, isLoading, error } = useTickets({ state: state || undefined, q: q || undefined, limit: 100 })

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Ticket queue</h1>
      <div className="flex flex-wrap gap-2">
        <label className="sr-only" htmlFor="ticket-search">Search tickets</label>
        <input
          id="ticket-search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search summary or description"
          className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
        />
        <label className="sr-only" htmlFor="ticket-state">Triage state</label>
        <select
          id="ticket-state"
          value={state}
          onChange={(e) => setState(e.target.value as TriageState | '')}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">All states</option>
          {STATES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      <ErrorBox error={error} />
      {isLoading && <Loading />}
      {data && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500 uppercase">
              <tr>
                <th className="px-3 py-2">#</th>
                <th className="px-3 py-2">Summary</th>
                <th className="px-3 py-2">Intake service</th>
                <th className="px-3 py-2">Entity</th>
                <th className="px-3 py-2">Priority</th>
                <th className="px-3 py-2">State</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((t) => (
                <tr key={t.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">{t.number}</td>
                  <td className="px-3 py-2">
                    <Link to={`/tickets/${t.id}`} className="text-blue-800 hover:underline">{t.summary}</Link>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">{t.affected_service ?? '-'}</td>
                  <td className="px-3 py-2">{t.business_entity ?? '-'}</td>
                  <td className="px-3 py-2"><PriorityPill level={t.priority} /></td>
                  <td className="px-3 py-2"><StatePill state={t.triage_state} /></td>
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
