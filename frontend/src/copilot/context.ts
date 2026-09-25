import { createContext, useContext } from 'react'

export interface TicketRef { id: string; number: number; summary: string }

export interface CopilotState {
  open: boolean
  setOpen: (open: boolean) => void
  /** The ticket currently on screen; the Copilot answers about it when set. */
  ticket: TicketRef | null
  setTicket: (ticket: TicketRef | null) => void
  /** Open the panel and ask right away. */
  ask: (question: string) => void
}

export const CopilotContext = createContext<CopilotState>({
  open: false, setOpen: () => {}, ticket: null, setTicket: () => {}, ask: () => {},
})

export const useCopilot = () => useContext(CopilotContext)
