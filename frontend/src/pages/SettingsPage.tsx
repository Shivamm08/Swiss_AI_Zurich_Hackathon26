import { useLlmModels, useReference, useSettings, useUsers } from '../api/hooks'
import { MatrixGrid } from '../components/triage'
import { Card, Loading } from '../components/ui'

export default function SettingsPage() {
  const { data: settings } = useSettings()
  const { data: users } = useUsers()
  const { data: models } = useLlmModels()
  const { data: reference } = useReference()
  if (!settings) return <Loading />

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-slate-500">Read-only for now; values come from the backend configuration (.env).</p>
      </header>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Routing">
          <dl className="grid grid-cols-2 gap-1 text-sm">
            <dt className="text-slate-500">Auto-assign at</dt><dd>≥ {Math.round(settings.auto_threshold * 100)}% confidence</dd>
            <dt className="text-slate-500">Needs review below</dt><dd>{Math.round(settings.triage_threshold * 100)}%</dd>
            <dt className="text-slate-500">Votes per ticket</dt><dd>{settings.votes}</dd>
            <dt className="text-slate-500">Max share per person</dt><dd>{Math.round(settings.max_share * 100)}%</dd>
            <dt className="text-slate-500">Default capacity</dt><dd>{settings.default_capacity} open tickets</dd>
            <dt className="text-slate-500">Default model</dt><dd>{models?.default_model ?? 'none (heuristic)'}</dd>
          </dl>
        </Card>
        <Card title="SLA targets">
          <dl className="grid grid-cols-2 gap-1 text-sm">
            {Object.entries(settings.sla_hours).map(([level, hours]) => (
              <div key={level} className="contents"><dt className="text-slate-500">{level}</dt><dd>{hours < 24 ? `${hours} h` : `${hours / 24} d`}</dd></div>
            ))}
          </dl>
        </Card>
        <Card title="Priority matrix (urgency × impact)">
          {reference && <MatrixGrid reference={reference} />}
        </Card>
      </div>
      <Card title={`Roster (${users?.length ?? 0})`}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-slate-500 uppercase"><tr><th className="py-1">Name</th><th>Role</th><th>Teams</th><th>Capacity</th></tr></thead>
            <tbody>
              {users?.map((u) => (
                <tr key={u.email} className="border-t border-slate-100">
                  <td className="py-1">{u.name} <span className="text-xs text-slate-400">{u.email}</span></td>
                  <td>{u.role}</td><td>{u.teams.join(', ') || '–'}</td><td className="tabular-nums">{u.capacity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
