import { createContext, useContext } from 'react'
import type { Role, Ticket, User } from '../api/types'

export interface Viewer {
  /** The person the app is being viewed as (demo stand-in for a login). */
  user: User | undefined
  role: Role
  setEmail: (email: string) => void
}

export const ViewerContext = createContext<Viewer>({ user: undefined, role: 'admin', setEmail: () => {} })

export const useViewer = () => useContext(ViewerContext)

/** Team Lead / Analyst and admin: check the AI triage, dispatch and reassign work. */
export const canDispatch = (role: Role) => role === 'analyst' || role === 'admin'

type TicketLike = Pick<Ticket, 'ai_team' | 'work_status' | 'triage_state' | 'route' | 'assignee'>

/** Waiting for any analyst: not triaged, low confidence, rejected, or no department yet (mirrors the backend). */
export const inNeedsReview = (t: TicketLike) =>
  t.work_status === 'open' && (t.triage_state === 'new' || t.triage_state === 'rejected' || t.route === 'triage' || !t.ai_team)

/** Decide on the AI proposal, dispatch, reassign, de-escalate: the admin, or the department's analyst
 *  (any analyst for the shared Needs-review pool). */
export const canManageTicket = (user: User | undefined, t: TicketLike) =>
  !!user && (user.role === 'admin' || (user.role === 'analyst' && (user.teams.includes(t.ai_team ?? '') || inNeedsReview(t))))

/** Escalate: the specialist on the ticket, or whoever can manage it. */
export const canEscalateTicket = (user: User | undefined, t: TicketLike) =>
  !!user && (canManageTicket(user, t) || user.email === t.assignee)
