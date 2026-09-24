import { useMemo, useState, type ReactNode } from 'react'
import { useLlmModels } from '../api/hooks'
import { HEURISTIC, ModelContext } from './context'

const STORAGE_KEY = 'llm-model'

function readStored(): string | undefined {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? undefined
  } catch {
    return undefined
  }
}

/** Remembers the chosen model per browser; each teammate picks their own. */
export default function ModelProvider({ children }: { children: ReactNode }) {
  const { data } = useLlmModels()
  const [stored, setStored] = useState<string | undefined>(readStored)

  // Drop a remembered model the backend no longer offers.
  const model = stored === HEURISTIC || (stored && data?.models.includes(stored)) ? stored : undefined

  const value = useMemo(
    () => ({
      model,
      setModel: (next: string | undefined) => {
        setStored(next)
        try {
          if (next) localStorage.setItem(STORAGE_KEY, next)
          else localStorage.removeItem(STORAGE_KEY)
        } catch {
          /* storage unavailable */
        }
      },
    }),
    [model],
  )
  return <ModelContext.Provider value={value}>{children}</ModelContext.Provider>
}
