import {
  BookOpen,
  FilePlus2,
  Inbox,
  LayoutDashboard,
  MessagesSquare,
  Settings,
  Sparkles,
  Upload,
  Users,
  type LucideIcon,
} from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useHealth, useTickets, useUsers } from '../api/hooks'
import type { Role } from '../api/types'
import { useViewer } from '../viewas/context'
import ModelPicker from './ModelPicker'

const NAV: { section: string; items: { to: string; label: string; icon: LucideIcon; end?: boolean; roles?: Role[] }[] }[] = [
  {
    section: 'Work',
    items: [
      { to: '/', label: 'Queue', icon: Inbox, end: true },
      { to: '/new', label: 'New ticket', icon: FilePlus2, roles: ['admin', 'lead'] },
      { to: '/team', label: 'Team workload', icon: Users, roles: ['lead', 'admin'] },
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    ],
  },
  {
    section: 'Knowledge',
    items: [
      { to: '/knowledge', label: 'Knowledge base', icon: BookOpen },
      { to: '/assistant', label: 'Assistant', icon: MessagesSquare },
    ],
  },
  {
    section: 'Admin',
    items: [
      { to: '/intake', label: 'Intake & export', icon: Upload, roles: ['admin', 'lead'] },
      { to: '/settings', label: 'Settings', icon: Settings, roles: ['admin'] },
    ],
  },
]

const ROLE_LABEL: Record<Role, string> = { admin: 'Admin', lead: 'Team lead', analyst: 'Analyst' }

function HealthIndicator() {
  const { data, isError } = useHealth()
  const ok = !isError && data?.database && data.llm_configured
  const label = isError ? 'Backend unreachable' : !data ? '…' : !data.database ? 'Database down' : data.llm_configured ? 'All systems go' : 'Heuristic mode'
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted" title={data ? `LLM: ${data.llm_provider} · ${data.llm_model ?? 'none'}` : undefined}>
      <span className={`h-2 w-2 rounded-full ${ok ? 'bg-emerald-500 shadow-[0_0_0_3px_rgb(16_185_129/0.15)]' : 'bg-amber-500'}`} />
      {label}
    </span>
  )
}

function ViewAsPicker() {
  const { data: users } = useUsers()
  const { user, setEmail } = useViewer()
  if (!users) return null
  const groups: Role[] = ['admin', 'lead', 'analyst']
  return (
    <label className="flex items-center gap-2 text-xs text-muted" htmlFor="view-as">
      View as
      <select
        id="view-as"
        value={user?.email ?? ''}
        onChange={(e) => setEmail(e.target.value)}
        className="max-w-60 rounded-lg border border-line bg-surface px-2 py-1 text-sm text-ink focus:border-accent focus:outline-none"
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

function NeedsReviewBadge() {
  const { user, role } = useViewer()
  const { data } = useTickets({ view: 'needs_review', as_user: user?.email, limit: 1 })
  if (role === 'analyst' || !data?.total) return null
  return <span className="ml-auto rounded-full bg-red-500 px-1.5 text-[11px] font-semibold text-white">{data.total}</span>
}

export default function Layout() {
  const { user, role } = useViewer()
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-ink text-slate-300 md:flex">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-ai to-accent text-white shadow-pop">
            <Sparkles size={17} />
          </span>
          <div className="leading-tight">
            <p className="font-semibold text-white">Triage Copilot</p>
            <p className="text-[11px] text-slate-400">AI service-desk assistant</p>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 pb-4">
          {NAV.map(({ section, items }) => {
            const visible = items.filter((n) => !n.roles || n.roles.includes(role))
            if (!visible.length) return null
            return (
              <div key={section} className="flex flex-col gap-0.5">
                <p className="px-3 pb-1 text-[10px] font-semibold tracking-[0.14em] text-slate-500 uppercase">{section}</p>
                {visible.map(({ to, label, icon: Icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    className={({ isActive }) =>
                      `group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition ${isActive ? 'bg-ink-2 font-medium text-white shadow-[inset_2px_0_0_var(--color-accent)]' : 'hover:bg-ink-2 hover:text-white'}`
                    }
                  >
                    <Icon size={16} className="shrink-0 opacity-80" />
                    {label}
                    {to === '/' && <NeedsReviewBadge />}
                  </NavLink>
                ))}
              </div>
            )
          })}
        </nav>
        <div className="border-t border-ink-3 px-5 py-4 text-xs">
          <p className="text-slate-400">Signed in as</p>
          <p className="truncate font-medium text-white">{user?.name ?? '…'}</p>
          <p className="text-slate-500">{ROLE_LABEL[role]}{user?.teams[0] ? ` · ${user.teams[0]}` : ''}</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex flex-wrap items-center gap-4 border-b border-line bg-surface/85 px-6 py-2.5 backdrop-blur">
          <span className="font-semibold md:hidden">Triage Copilot</span>
          <HealthIndicator />
          <div className="ml-auto flex flex-wrap items-center gap-4">
            <ViewAsPicker />
            <ModelPicker />
          </div>
        </header>
        {/* compact nav for small screens */}
        <nav className="flex gap-1 overflow-x-auto border-b border-line bg-surface px-3 py-2 md:hidden">
          {NAV.flatMap((s) => s.items).filter((n) => !n.roles || n.roles.includes(role)).map(({ to, label, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) => `rounded-md px-2.5 py-1 text-sm whitespace-nowrap ${isActive ? 'bg-accent-soft text-accent' : 'text-muted'}`}>
              {label}
            </NavLink>
          ))}
        </nav>
        <main className="mx-auto w-full max-w-[1500px] flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
