import { NavLink, Outlet } from 'react-router-dom'
import { useHealth, useUsers } from '../api/hooks'
import type { Role } from '../api/types'
import { useViewer } from '../viewas/context'
import ModelPicker from './ModelPicker'
import { Pill } from './ui'

const NAV: { to: string; label: string; end?: boolean; roles?: Role[] }[] = [
  { to: '/', label: 'Queue', end: true },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/team', label: 'Team workload', roles: ['lead', 'admin'] },
  { to: '/new', label: 'New ticket', roles: ['admin'] },
  { to: '/knowledge', label: 'Knowledge base' },
  { to: '/assistant', label: 'Assistant' },
  { to: '/intake', label: 'Intake & export' },
  { to: '/settings', label: 'Settings', roles: ['admin'] },
]

const ROLE_LABEL: Record<Role, string> = { admin: 'Admin', lead: 'Team lead', analyst: 'Analyst' }

function HealthIndicator() {
  const { data, isError } = useHealth()
  if (isError) return <Pill className="bg-red-100 text-red-800">Backend unreachable</Pill>
  if (!data) return null
  return (
    <Pill className={data.database && data.llm_configured ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}>
      {data.database ? '● DB' : '○ DB down'} · {data.llm_configured ? 'LLM' : 'Heuristic mode'}
    </Pill>
  )
}

function ViewAsPicker() {
  const { data: users } = useUsers()
  const { user, setEmail } = useViewer()
  if (!users) return null
  const groups: Role[] = ['admin', 'lead', 'analyst']
  return (
    <label className="flex items-center gap-2 text-xs text-slate-300" htmlFor="view-as">
      View as
      <select
        id="view-as"
        value={user?.email ?? ''}
        onChange={(e) => setEmail(e.target.value)}
        className="max-w-56 rounded-md border border-slate-600 bg-slate-800 px-2 py-1 text-sm text-white"
      >
        {groups.map((role) => (
          <optgroup key={role} label={ROLE_LABEL[role]}>
            {users.filter((u) => u.role === role).map((u) => (
              <option key={u.email} value={u.email}>
                {u.name}{u.teams.length ? ` · ${u.teams[0]}` : ''}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  )
}

export default function Layout() {
  const { role } = useViewer()
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 flex flex-wrap items-center gap-3 bg-slate-900 px-4 py-2 text-white">
        <span className="font-semibold">Triage Copilot</span>
        <span className="text-xs text-slate-400">Swiss Life service desk</span>
        <div className="ml-auto flex flex-wrap items-center gap-3">
          <ViewAsPicker />
          <ModelPicker />
          <HealthIndicator />
        </div>
      </header>
      <div className="flex flex-1 flex-col md:flex-row">
        <nav className="flex flex-wrap gap-1 border-b border-slate-200 bg-white p-3 md:w-48 md:flex-col md:border-r md:border-b-0">
          {NAV.filter((n) => !n.roles || n.roles.includes(role)).map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm ${isActive ? 'bg-blue-50 font-medium text-blue-800' : 'text-slate-700 hover:bg-slate-100'}`
              }
            >
              {label}
            </NavLink>
          ))}
          <span className="mt-auto hidden px-3 pt-4 text-xs text-slate-400 md:block">Viewing as {ROLE_LABEL[role]}</span>
        </nav>
        <main className="min-w-0 flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
