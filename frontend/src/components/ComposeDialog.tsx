// "Escalate / Message" from a ticket: pick who and why, Copilot drafts the message,
// then the Messages screen opens with the draft ready to edit and send.
import { ArrowRightLeft, HelpCircle, Loader2, Siren, Sparkles, X } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDirectory, useDraftMessage } from '../api/hooks'
import type { DraftRequest, TicketDetail } from '../api/types'
import { useSelectedModel } from '../model/context'
import { useViewer } from '../viewas/context'
import { Avatar } from './people'
import { Button, ErrorBox } from './ui'

type Purpose = DraftRequest['purpose']

const PURPOSES: { key: Purpose; label: string; hint: string; icon: typeof Siren }[] = [
  { key: 'escalate', label: 'Escalate', hint: 'Ask someone to take ownership now', icon: Siren },
  { key: 'handoff', label: 'Hand off', hint: 'Pass the ticket on with full context', icon: ArrowRightLeft },
  { key: 'question', label: 'Ask a question', hint: 'Get missing information', icon: HelpCircle },
]

export default function ComposeDialog({ ticket, initialPurpose, onClose }: { ticket: TicketDetail; initialPurpose: Purpose; onClose: () => void }) {
  const navigate = useNavigate()
  const { user } = useViewer()
  const { model } = useSelectedModel()
  const { data: departments } = useDirectory()
  const draft = useDraftMessage()
  const [purpose, setPurpose] = useState<Purpose>(initialPurpose)
  const team = ticket.ai_team ?? undefined
  const dept = departments?.find((d) => d.team === team)
  const options = [
    ...(dept?.lead ? [{ to: dept.lead.email, label: dept.lead.name, sub: `Team Lead / Analyst · ${team}` }] : []),
    ...(ticket.assignee && ticket.assignee !== dept?.lead?.email
      ? [{ to: ticket.assignee, label: dept?.members.find((m) => m.email === ticket.assignee)?.name ?? ticket.assignee, sub: 'Working on this ticket' }] : []),
    ...(team ? [{ to: `team:${team}`, label: `${team} channel`, sub: 'Everyone in the department' }] : []),
  ].filter((o) => o.to !== user?.email)
  const [to, setTo] = useState('')
  const selected = to || options[0]?.to || ''

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
          <div className="grid grid-cols-3 gap-2">
            {PURPOSES.map(({ key, label, hint, icon: Icon }) => (
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
            Copilot writes the message with the ticket's context (what's affected, priority, SLA, proposed fix). You review it before sending.
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
