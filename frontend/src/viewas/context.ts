import { createContext, useContext } from 'react'
import type { Role, User } from '../api/types'

export interface Viewer {
  /** The person the app is being viewed as (demo stand-in for a login). */
  user: User | undefined
  role: Role
  setEmail: (email: string) => void
}

export const ViewerContext = createContext<Viewer>({ user: undefined, role: 'admin', setEmail: () => {} })

export const useViewer = () => useContext(ViewerContext)

export const canLead = (role: Role) => role === 'lead' || role === 'admin'
