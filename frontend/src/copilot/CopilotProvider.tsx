import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useCopilotChat } from '../api/copilot'
import { useSelectedModel } from '../model/context'
import CopilotPanel from './CopilotPanel'
import { CopilotContext, type TicketRef } from './context'

/** Keeps one Copilot conversation alive across pages; ⌘K / Ctrl+K toggles the panel. */
export default function CopilotProvider({ children }: { children: ReactNode }) {
  const chat = useCopilotChat()
  const { model } = useSelectedModel()
  const [open, setOpen] = useState(false)
  const [ticket, setTicket] = useState<TicketRef | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setOpen((v) => !v) }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const { send } = chat
  const ask = useCallback((question: string) => {
    setOpen(true)
    send(question, { ticketId: ticket?.id, model })
  }, [send, ticket, model])

  const value = useMemo(() => ({ open, setOpen, ticket, setTicket, ask }), [open, ticket, ask])
  return (
    <CopilotContext.Provider value={value}>
      {children}
      <CopilotPanel open={open} onClose={() => setOpen(false)} messages={chat.messages} busy={chat.busy}
        onSend={(text) => chat.send(text, { ticketId: ticket?.id, model })} onStop={chat.stop} onClear={chat.clear}
        ticket={ticket} onClearTicket={() => setTicket(null)} />
    </CopilotContext.Provider>
  )
}
