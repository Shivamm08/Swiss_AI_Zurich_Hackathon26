import {
  BarChart3,
  BookOpen,
  FilePlus2,
  Inbox,
  MessageSquare,
  Settings,
  Sparkles,
  Upload,
  Users,
  UsersRound,
  type LucideIcon,
} from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useChannels, useHealth, useTickets } from '../api/hooks'
import type { Role } from '../api/types'
import { useCopilot } from '../copilot/context'
import { useViewer } from '../viewas/context'
import ModelPicker from './ModelPicker'
import PersonaSwitcher from './PersonaSwitcher'
import { ROLE_LABEL } from './styles'

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean; roles?: Role[]; badge?: 'review' | 'messages' }

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: 'Workspace',
    items: [
      { to: '/', label: 'Queue', icon: Inbox, end: true, badge: 'review' },
      { to: '/messages', label: 'Messages', icon: MessageSquare, badge: 'messages' },
      { to: '/people', label: 'People & teams', icon: UsersRound },
    ],
  },
  {
    section: 'Manage',
    items: [
      { to: '/new', label: 'New ticket', icon: FilePlus2, roles: ['analyst', 'admin'] },
      { to: '/team', label: 'Team workload', icon: Users, roles: ['analyst', 'admin'] },
      { to: '/dashboard', label: 'Impact', icon: BarChart3, roles: ['analyst', 'admin'] },
    ],
  },
  {
    section: 'Administration',
    items: [
      { to: '/knowledge', label: 'Knowledge base', icon: BookOpen, roles: ['admin'] },
      { to: '/intake', label: 'Intake & export', icon: Upload, roles: ['admin'] },
      { to: '/settings', label: 'Settings', icon: Settings, roles: ['admin'] },
    ],
  },
]

function HealthDot() {
  const { data, isError } = useHealth()
  const ok = !isError && data?.database && data.llm_configured
  const label = isError ? 'Backend unreachable' : !data ? '…' : !data.database ? 'Database down' : data.llm_configured ? 'All systems go' : 'Heuristic mode'
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <span className={`h-2 w-2 rounded-full ${ok ? 'bg-emerald-500 shadow-[0_0_0_3px_rgb(16_185_129/0.15)]' : 'bg-amber-500'}`} />
      <span className="hidden lg:inline">{label}</span>
    </span>
  )
}

function Badge({ kind }: { kind: NonNullable<NavItem['badge']> }) {
  const { user, role } = useViewer()
  const specialist = role === 'specialist'
  // Specialists: their open work. Analysts and admin: tickets waiting for a decision.
  const { data: inbox } = useTickets({ view: 'inbox', as_user: user?.email, limit: 1 })
  const { data: review } = useTickets({ view: 'needs_review', as_user: user?.email, limit: 1 })
  const { data: mine } = useTickets({ view: 'mine', as_user: user?.email, limit: 1 })
  const { data: channels } = useChannels(kind === 'messages' ? user?.email : undefined)
  if (kind === 'messages') {
    const dms = channels?.filter((c) => c.kind === 'dm').length ?? 0
    return dms ? <span className="ml-auto rounded-full bg-ink-3 px-1.5 text-[11px] font-semibold text-slate-200">{dms}</span> : null
  }
  const n = specialist ? mine?.total : (inbox?.total ?? 0) + (review?.total ?? 0)
  if (!n) return null
  return <span className={`ml-auto rounded-full px-1.5 text-[11px] font-semibold ${specialist ? 'bg-accent text-white' : 'bg-red-500 text-white'}`}>{n}</span>
}

export default function Layout() {
  const { user, role } = useViewer()
  const copilot = useCopilot()
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-ink text-slate-300 md:flex">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-ai to-accent text-white shadow-pop">
            <Sparkles size={18} />
          </span>
          <div className="leading-tight">
            <p className="font-semibold text-white">Triage Copilot</p>
            <p className="text-[11px] text-slate-400">AI service-desk assistant</p>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-6 overflow-y-auto px-3 pb-4">
          {NAV.map(({ section, items }) => {
            const visible = items.filter((n) => !n.roles || n.roles.includes(role))
            if (!visible.length) return null
            return (
              <div key={section} className="flex flex-col gap-0.5">
                <p className="px-3 pb-1.5 text-[10px] font-semibold tracking-[0.16em] text-slate-500 uppercase">{section}</p>
                {visible.map(({ to, label, icon: Icon, end, badge }) => (
                  <NavLink key={to} to={to} end={end}
                    className={({ isActive }) =>
                      `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${isActive ? 'bg-ink-2 font-medium text-white shadow-[inset_3px_0_0_var(--color-accent)]' : 'hover:bg-ink-2/70 hover:text-white'}`}>
                    <Icon size={17} className="shrink-0 opacity-80" />
                    {label}
                    {badge && <Badge kind={badge} />}
                  </NavLink>
                ))}
              </div>
            )
          })}
          <button type="button" onClick={() => copilot.setOpen(true)}
            className="mt-auto flex items-center gap-3 rounded-xl bg-gradient-to-r from-ai/25 to-accent/25 px-3 py-3 text-left ring-1 ring-white/10 transition hover:from-ai/35 hover:to-accent/35">
            <Sparkles size={17} className="text-white" />
            <span className="flex-1">
              <span className="block text-sm font-medium text-white">Ask Copilot</span>
              <span className="block text-[11px] text-slate-400">Answers from team knowledge</span>
            </span>
            <kbd className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-slate-300">⌘K</kbd>
          </button>
        </nav>
        <div className="border-t border-ink-3 px-5 py-3.5 text-xs">
          <p className="truncate font-medium text-white">{user?.name ?? '…'}</p>
          <p className="text-slate-500">{ROLE_LABEL[role]}{user?.teams[0] ? ` · ${user.teams[0]}` : ''}</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-surface/85 px-4 py-2.5 backdrop-blur md:px-6">
          <span className="font-semibold md:hidden">Triage Copilot</span>
          <HealthDot />
          <div className="ml-auto flex items-center gap-3">
            <ModelPicker />
            <button type="button" onClick={() => copilot.setOpen(!copilot.open)}
              className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-ai to-accent px-3.5 py-1.5 text-sm font-medium text-white shadow-sm transition hover:brightness-110">
              <Sparkles size={14} />Copilot
            </button>
            <PersonaSwitcher />
          </div>
        </header>
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
