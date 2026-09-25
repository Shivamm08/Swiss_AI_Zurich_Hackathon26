// "View as" persona switcher: a searchable panel grouped by department, with quick demo picks.
import { Check, ChevronDown, Search, ShieldCheck, Star, Users, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useDirectory, useUsers } from '../api/hooks'
import type { User } from '../api/types'
import { useViewer } from '../viewas/context'
import { Avatar, LoadBar } from './people'
import { ROLE_LABEL } from './styles'
import { Pill } from './ui'

const ROLE_STYLE = {
  admin: 'bg-ink text-white',
  analyst: 'bg-accent-soft text-accent',
  specialist: 'bg-slate-100 text-slate-700',
} as const

function PersonRow({ user, open, capacity, active, onPick }: { user: User; open?: number; capacity?: number; active: boolean; onPick: () => void }) {
  return (
    <button type="button" onClick={onPick}
      className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition ${active ? 'bg-accent-soft ring-1 ring-accent/30' : 'hover:bg-canvas'}`}>
      <Avatar name={user.name} email={user.email} size="sm" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{user.name}</span>
        <span className="block truncate text-[11px] text-muted">{user.email}</span>
      </span>
      {open !== undefined && capacity !== undefined && user.role === 'specialist' && <LoadBar open={open} capacity={capacity} />}
      <Pill className={ROLE_STYLE[user.role]}>{ROLE_LABEL[user.role]}</Pill>
      {active && <Check size={15} className="text-accent" />}
    </button>
  )
}

export default function PersonaSwitcher() {
  const { data: users } = useUsers()
  const { data: departments } = useDirectory()
  const { user, setEmail } = useViewer()
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const load = useMemo(() => {
    const map = new Map<string, { open: number; capacity: number }>()
    departments?.forEach((d) => d.members.forEach((m) => map.set(m.email, { open: m.open, capacity: m.capacity })))
    return map
  }, [departments])

  const quickPicks = useMemo(() => {
    if (!users) return []
    const admin = users.find((u) => u.role === 'admin')
    const deptOpen = new Map<string, number>(departments?.map((d) => [d.team, d.open_tickets]) ?? [])
    const analyst = users.filter((u) => u.role === 'analyst').sort((a, b) => (deptOpen.get(b.teams[0] ?? '') ?? 0) - (deptOpen.get(a.teams[0] ?? '') ?? 0))[0]
    const specialist = users.filter((u) => u.role === 'specialist').sort((a, b) => (load.get(b.email)?.open ?? 0) - (load.get(a.email)?.open ?? 0))[0]
    return [
      admin && { user: admin, why: 'Sees everything: knowledge base, intake, settings' },
      analyst && { user: analyst, why: `Team Lead / Analyst · ${analyst.teams[0] ?? ''}: checks the AI triage and dispatches work` },
      specialist && { user: specialist, why: `Specialist · ${specialist.teams[0] ?? ''}: busiest queue right now` },
    ].filter(Boolean) as { user: User; why: string }[]
  }, [users, load, departments])

  const pick = (email: string) => { setEmail(email); setOpen(false); setQ('') }
  const match = (u: User) => !q || `${u.name} ${u.email} ${u.teams.join(' ')} ${u.role}`.toLowerCase().includes(q.toLowerCase())

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}
        className="flex items-center gap-2 rounded-full border border-line bg-surface py-1 pr-3 pl-1 text-sm shadow-card transition hover:border-accent/40">
        {user && <Avatar name={user.name} email={user.email} size="xs" />}
        <span className="hidden max-w-40 truncate font-medium sm:inline">{user?.name ?? 'Choose persona'}</span>
        {user && <span className="hidden md:inline"><Pill className={ROLE_STYLE[user.role]}>{ROLE_LABEL[user.role]}</Pill></span>}
        <ChevronDown size={14} className="text-muted" />
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-ink/40 p-4 pt-[8vh] backdrop-blur-sm" onClick={() => setOpen(false)}>
          <div role="dialog" aria-modal="true" aria-label="Switch persona"
            className="animate-rise flex max-h-[80vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl bg-surface shadow-pop" onClick={(e) => e.stopPropagation()}>
            <header className="flex items-center gap-3 border-b border-line px-5 py-4">
              <Users size={18} className="text-accent" />
              <div className="flex-1">
                <p className="font-semibold">Switch persona</p>
                <p className="text-xs text-muted">See the app through anyone's eyes. Roles change what's visible: team leads / analysts check the AI triage and dispatch work, specialists do the work and close tickets, the admin runs the system.</p>
              </div>
              <button type="button" onClick={() => setOpen(false)} className="rounded-lg p-1.5 text-muted hover:bg-canvas" aria-label="Close"><X size={18} /></button>
            </header>
            <div className="border-b border-line px-5 py-3">
              <label className="relative block" htmlFor="persona-search">
                <span className="sr-only">Search people</span>
                <Search size={15} className="pointer-events-none absolute top-2.5 left-3 text-muted" />
                <input id="persona-search" autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, team or role"
                  className="w-full rounded-lg border border-line bg-canvas py-2 pr-3 pl-9 text-sm focus:border-accent focus:bg-surface focus:outline-none" />
              </label>
            </div>
            <div className="overflow-y-auto px-5 py-4">
              {!q && quickPicks.length > 0 && (
                <section className="mb-5">
                  <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-muted uppercase"><Star size={12} />Demo personas</p>
                  <div className="grid gap-2 md:grid-cols-3">
                    {quickPicks.map(({ user: u, why }) => (
                      <button key={u.email} type="button" onClick={() => pick(u.email)}
                        className={`flex items-start gap-3 rounded-xl border p-3 text-left transition hover:border-accent/50 hover:shadow-card ${user?.email === u.email ? 'border-accent bg-accent-soft/50' : 'border-line'}`}>
                        {u.role === 'admin' ? <span className="grid h-10 w-10 place-items-center rounded-full bg-ink text-white"><ShieldCheck size={18} /></span> : <Avatar name={u.name} email={u.email} size="md" />}
                        <span className="min-w-0">
                          <span className="block font-medium">{u.name}</span>
                          <span className="block text-xs text-muted">{why}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </section>
              )}
              {users?.filter((u) => u.role === 'admin' && match(u)).map((u) => (
                <section key={u.email} className="mb-4">
                  <p className="mb-1 text-[11px] font-semibold tracking-wider text-muted uppercase">Administration</p>
                  <PersonRow user={u} active={user?.email === u.email} onPick={() => pick(u.email)} />
                </section>
              ))}
              <div className="grid gap-x-6 gap-y-4 md:grid-cols-2">
                {departments?.map((d) => {
                  const people = (users ?? []).filter((u) => u.teams.includes(d.team) && match(u))
                    .sort((a, b) => (a.role === 'analyst' ? -1 : b.role === 'analyst' ? 1 : a.name.localeCompare(b.name)))
                  if (!people.length) return null
                  return (
                    <section key={d.team}>
                      <p className="mb-1 flex items-center justify-between text-[11px] font-semibold tracking-wider text-muted uppercase">
                        {d.team}<span className="font-normal normal-case">{d.open_tickets} open</span>
                      </p>
                      <div className="flex flex-col gap-0.5">
                        {people.map((u) => (
                          <PersonRow key={u.email} user={u} open={load.get(u.email)?.open} capacity={load.get(u.email)?.capacity}
                            active={user?.email === u.email} onPick={() => pick(u.email)} />
                        ))}
                      </div>
                    </section>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
