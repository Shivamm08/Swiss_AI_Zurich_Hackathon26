// "Escalate / Ask a question" from a ticket: pick who, Copilot drafts the message, then the
// Messages screen opens with the draft ready to edit and send. Escalations go one level up:
// specialist -> their Team Lead / Analyst, analyst -> the admin. (Hand-offs aren't messages any
// more: a specialist hands a ticket back from the work bar.)
import { HelpCircle, Loader2, Siren, Sparkles, X } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDirectory, useDraftMessage, useUsers } from '../api/hooks'
import type { DraftRequest, TicketDetail } from '../api/types'
import { useSelectedModel } from '../model/context'
import { canEscalateTicket, useViewer } from '../viewas/context'
import { Avatar } from './people'
import { Button, ErrorBox } from './ui'

type Purpose = DraftRequest['purpose']

const PURPOSES: { key: Purpose; label: string; hint: string; icon: typeof Siren }[] = [
  { key: 'escalate', label: 'Escalate', hint: 'Flag it and alert the next level up: SLA at risk, blocked, needs a decision', icon: Siren },
  { key: 'question', label: 'Ask a question', hint: 'Get missing information. Changes nothing on the ticket', icon: HelpCircle },
]

type Option = { to: string; label: string; sub: string }

export default function ComposeDialog({ ticket, initialPurpose, onClose }: { ticket: TicketDetail; initialPurpose: Purpose; onClose: () => void }) {
  const navigate = useNavigate()
  const { user, role } = useViewer()
  const { model } = useSelectedModel()
  const { data: departments } = useDirectory()
  const { data: users } = useUsers()
  const draft = useDraftMessage()
  const mayEscalate = canEscalateTicket(user, ticket)
  const purposes = PURPOSES.filter((p) => p.key !== 'escalate' || mayEscalate)
  const [picked, setPurpose] = useState<Purpose>(initialPurpose)
  const purpose: Purpose = mayEscalate ? picked : 'question'
  const team = ticket.ai_team ?? undefined
  const dept = departments?.find((d) => d.team === team)
  const admin = users?.find((u) => u.role === 'admin')
  const lead: Option | null = dept?.lead ? { to: dept.lead.email, label: dept.lead.name, sub: `Team Lead / Analyst · ${team}` } : null
  const desk: Option | null = admin ? { to: admin.email, label: admin.name, sub: 'Admin · desk owner' } : null
  const channel: Option | null = team ? { to: `team:${team}`, label: `${team} channel`, sub: 'Everyone in the department' } : null
  const worker: Option | null = ticket.assignee
    ? { to: ticket.assignee, label: dept?.members.find((m) => m.email === ticket.assignee)?.name ?? ticket.assignee, sub: 'Specialist on this ticket' } : null
  // Escalations go one level up; questions can go to anyone involved.
  const candidates = purpose === 'escalate'
    ? (role === 'analyst' ? [desk, channel] : [lead, channel])
    : [lead, worker, channel]
  const options = candidates.filter((o): o is Option => !!o && o.to !== user?.email)
  const [to, setTo] = useState('')
  const selected = options.some((o) => o.to === to) ? to : options[0]?.to ?? ''

  const go = () => draft.mutate(
    { ticket_id: ticket.id, sender: user!.email, to: selected, purpose, model },
    { onSuccess: (d) => navigate(`/messages?channel=${encodeURIComponent(d.channel)}`, { state: { draft: d.body, ticketId: ticket.id, kind: d.kind } }) },
  )

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-ink/40 p-4 pt-[10vh] backdrop-blur-sm" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Message about this ticket" className="animate-rise w-full max-w-lg rounded-2xl bg-surface shadow-pop" onClick={(e) => e.stopPropagation()}>
        <header className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <p className="font-semibold">Message about #{ticket.number}</p>
          <button type="button" onClick={onClose} className="rounded-lg p-1.5 text-muted hover:bg-canvas" aria-label="Close"><X size={18} /></button>
        </header>
        <div className="flex flex-col gap-4 px-5 py-4">
          <div className={`grid gap-2 ${purposes.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
            {purposes.map(({ key, label, hint, icon: Icon }) => (
              <button key={key} type="button" onClick={() => setPurpose(key)}
                className={`flex flex-col items-start gap-1 rounded-xl border p-3 text-left transition ${purpose === key ? (key === 'escalate' ? 'border-red-300 bg-red-50' : 'border-accent/50 bg-accent-soft/50') : 'border-line hover:bg-canvas'}`}>
                <Icon size={16} className={key === 'escalate' ? 'text-red-600' : 'text-accent'} />
                <span className="text-sm font-medium">{label}</span>
                <span className="text-[11px] leading-tight text-muted">{hint}</span>
              </button>
            ))}
          </div>
          <div>
            <p className="mb-1.5 text-xs font-medium text-muted">To</p>
            {options.length === 0 ? <p className="text-sm text-muted">Triage the ticket first so we know which team owns it.</p> : (
              <div className="flex flex-col gap-1">
                {options.map((o) => (
                  <label key={o.to} className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 ${selected === o.to ? 'border-accent/50 bg-accent-soft/40' : 'border-line'}`}>
                    <input type="radio" name="compose-to" value={o.to} checked={selected === o.to} onChange={() => setTo(o.to)} className="accent-accent" />
                    <Avatar name={o.label} email={o.to.startsWith('team:') ? undefined : o.to} size="xs" />
                    <span className="text-sm"><b className="font-medium">{o.label}</b> <span className="text-muted">· {o.sub}</span></span>
                  </label>
                ))}
              </div>
            )}
          </div>
          <p className="flex items-start gap-2 rounded-lg bg-ai-soft/60 px-3 py-2 text-xs text-ai">
            <Sparkles size={14} className="mt-0.5 shrink-0" />
            Copilot writes the message with the ticket's context (what's affected, priority, SLA, who's on it). You review it before sending.
            {purpose === 'escalate' && ' Sending it marks the ticket escalated until the Team Lead / Analyst de-escalates it.'}
          </p>
          <ErrorBox error={draft.error} />
        </div>
        <footer className="flex justify-end gap-2 border-t border-line px-5 py-3">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant={purpose === 'escalate' ? 'danger' : 'ai'} disabled={!options.length || draft.isPending} onClick={go}
            icon={draft.isPending ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}>
            {draft.isPending ? 'Copilot is drafting…' : 'Draft with Copilot'}
          </Button>
        </footer>
      </div>
    </div>
  )
}
