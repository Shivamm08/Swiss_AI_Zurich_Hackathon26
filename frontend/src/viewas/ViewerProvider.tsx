import { useMemo, useState, type ReactNode } from 'react'
import { useUsers } from '../api/hooks'
import { ViewerContext } from './context'

const STORAGE_KEY = 'view-as'
const DEFAULT_EMAIL = 'admin@intcom.com'

function readStored(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? DEFAULT_EMAIL
  } catch {
    return DEFAULT_EMAIL
  }
}

/** "View as" switcher state, remembered per browser. No real authentication (by design, for the demo). */
export default function ViewerProvider({ children }: { children: ReactNode }) {
  const { data: users } = useUsers()
  const [email, setEmailState] = useState(readStored)
  const user = users?.find((u) => u.email === email) ?? users?.find((u) => u.email === DEFAULT_EMAIL) ?? users?.[0]

  const value = useMemo(
    () => ({
      user,
      role: user?.role ?? 'admin',
      setEmail: (next: string) => {
        setEmailState(next)
        try {
          localStorage.setItem(STORAGE_KEY, next)
        } catch {
          /* storage unavailable */
        }
      },
    }),
    [user],
  )
  return <ViewerContext.Provider value={value}>{children}</ViewerContext.Provider>
}
