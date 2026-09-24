import { NavLink, Outlet } from 'react-router-dom'
import { useHealth } from '../api/hooks'
import ModelPicker from './ModelPicker'
import { Pill } from './ui'

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/tickets', label: 'Ticket queue' },
  { to: '/knowledge', label: 'Knowledge base' },
  { to: '/assistant', label: 'Assistant' },
  { to: '/import', label: 'Import & export' },
]

function HealthIndicator() {
  const { data, isError } = useHealth()
  if (isError) return <Pill className="bg-red-100 text-red-800">Backend unreachable</Pill>
  if (!data) return null
  return (
    <div className="flex flex-wrap gap-1">
      <Pill className={data.database ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}>
        DB {data.database ? 'ok' : 'down'}
      </Pill>
      <Pill className={data.llm_configured ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}>
        {data.llm_configured ? `LLM: ${data.llm_provider} · ${data.llm_model}` : 'Heuristic mode'}
      </Pill>
    </div>
  )
}

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="flex flex-col gap-4 border-b border-slate-200 bg-white p-4 md:w-56 md:border-r md:border-b-0">
        <div>
          <p className="text-xs tracking-wider text-slate-500 uppercase">Swiss Life</p>
          <h1 className="font-semibold">Triage Agent</h1>
        </div>
        <nav className="flex flex-wrap gap-1 md:flex-col">
          {NAV.map(({ to, label, end }) => (
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
        </nav>
        <div className="flex flex-col gap-3 md:mt-auto">
          <ModelPicker />
          <HealthIndicator />
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  )
}
