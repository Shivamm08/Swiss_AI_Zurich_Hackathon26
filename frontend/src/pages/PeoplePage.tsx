import { Building2, Hash, MessageSquare, Search, ShieldAlert, Ticket as TicketIcon, X } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDirectory } from '../api/hooks'
import type { Department } from '../api/types'
import { Avatar, AvatarStack, LoadBar } from '../components/people'
import { ROLE_LABEL } from '../components/styles'
import { Button, Card, EmptyState, Loading, PageHeader, Pill } from '../components/ui'
import { useViewer } from '../viewas/context'

const dm = (a: string, b: string) => `dm:${[a.toLowerCase(), b.toLowerCase()].sort().join('|')}`

function DepartmentDrawer({ dept, onClose }: { dept: Department; onClose: () => void }) {
  const navigate = useNavigate()
  const { user } = useViewer()
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink/30 backdrop-blur-[2px]" onClick={onClose}>
      <aside className="animate-rise flex h-full w-full max-w-lg flex-col bg-surface shadow-pop" onClick={(e) => e.stopPropagation()}>
        <header className="flex items-start gap-3 border-b border-line px-5 py-4">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-ink text-white"><Building2 size={18} /></span>
          <div className="flex-1">
            <p className="text-lg font-semibold">{dept.team}</p>
            <p className="text-xs text-muted">{dept.members.length} people · {dept.open_tickets} open tickets · {dept.escalations} escalations</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1.5 text-muted hover:bg-canvas" aria-label="Close"><X size={18} /></button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <p className="mb-2 text-[11px] font-semibold tracking-wider text-muted uppercase">Owns these services</p>
          <div className="mb-5 flex flex-wrap gap-1.5">
            {dept.services.map((s) => (
              <Pill key={s.name} className={s.criticality === 'Critical' ? 'bg-red-50 text-red-700 ring-1 ring-red-200' : 'bg-slate-100 text-slate-700'}>
                {s.name}{s.criticality === 'Critical' && ' · critical'}
              </Pill>
            ))}
          </div>
          <p className="mb-2 text-[11px] font-semibold tracking-wider text-muted uppercase">People</p>
          <ul className="flex flex-col divide-y divide-line rounded-xl border border-line">
            {dept.members.map((m) => (
              <li key={m.email} className="flex items-center gap-3 px-3 py-2.5">
                <Avatar name={m.name} email={m.email} size="md" />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{m.name}</span>
                  <span className="block text-xs text-muted">{ROLE_LABEL[m.role]} · {m.email}</span>
                </span>
                <LoadBar open={m.open} capacity={m.capacity} />
                {m.email !== user?.email && (
                  <Button variant="ghost" className="px-2" icon={<MessageSquare size={15} />} onClick={() => navigate(`/messages?channel=${encodeURIComponent(dm(user!.email, m.email))}`)}>
                    <span className="sr-only">Message {m.name}</span>
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </div>
        <footer className="flex gap-2 border-t border-line px-5 py-3">
          <Button icon={<Hash size={15} />} onClick={() => navigate(`/messages?channel=${encodeURIComponent(dept.channel)}`)}>Open team channel</Button>
          <Button variant="secondary" icon={<TicketIcon size={15} />} onClick={() => navigate('/')}>View queue</Button>
        </footer>
      </aside>
    </div>
  )
}

export default function PeoplePage() {
  const { data, isLoading } = useDirectory()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState<Department | null>(null)
  const depts = (data ?? []).filter((d) => !q || `${d.team} ${d.services.map((s) => s.name).join(' ')} ${d.members.map((m) => m.name).join(' ')}`
    .toLowerCase().includes(q.toLowerCase()))

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="People & teams" subtitle="Every department, what it owns, who's in it and how busy they are. Message a team or a person directly."
        actions={
          <label className="relative" htmlFor="people-search">
            <span className="sr-only">Search</span>
            <Search size={15} className="pointer-events-none absolute top-2.5 left-2.5 text-muted" />
            <input id="people-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search teams, services, people"
              className="w-64 rounded-lg border border-line bg-surface py-1.5 pr-3 pl-8 text-sm focus:border-accent focus:outline-none" />
          </label>
        } />
      {isLoading && <Loading />}
      {data && depts.length === 0 && <EmptyState title="No match" />}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {depts.map((d) => (
          <Card key={d.team} className="flex flex-col transition hover:shadow-pop">
            <div className="flex items-start gap-3">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-ink text-white"><Building2 size={18} /></span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{d.team}</p>
                <p className="truncate text-xs text-muted">{d.services.map((s) => s.name).join(' · ')}</p>
              </div>
              {d.escalations > 0 && <Pill className="bg-red-50 text-red-700 ring-1 ring-red-200"><ShieldAlert size={11} />{d.escalations}</Pill>}
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              {[['Open', d.open_tickets], ['People', d.members.length], ['Msgs / 7d', d.messages_7d]].map(([label, value]) => (
                <div key={label} className="rounded-lg bg-canvas py-2">
                  <p className="text-lg font-semibold tabular">{value}</p>
                  <p className="text-[11px] text-muted">{label}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-2">
              {d.lead && <><Avatar name={d.lead.name} email={d.lead.email} size="xs" /><span className="text-xs"><b>{d.lead.name}</b> <span className="text-muted">lead</span></span></>}
              <span className="ml-auto"><AvatarStack people={d.members} /></span>
            </div>
            <div className="mt-4 flex gap-2 border-t border-line pt-3">
              <Button variant="secondary" className="flex-1" onClick={() => setOpen(d)}>View team</Button>
              <Button className="flex-1" icon={<MessageSquare size={14} />} onClick={() => navigate(`/messages?channel=${encodeURIComponent(d.channel)}`)}>Message</Button>
            </div>
          </Card>
        ))}
      </div>
      {open && <DepartmentDrawer dept={open} onClose={() => setOpen(null)} />}
    </div>
  )
}
