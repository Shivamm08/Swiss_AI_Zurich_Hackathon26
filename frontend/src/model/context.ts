import { createContext, useContext } from 'react'

export const HEURISTIC = 'heuristic'

export interface ModelSelection {
  /** Model sent with AI requests; undefined = backend default. */
  model: string | undefined
  setModel: (model: string | undefined) => void
}

export const ModelContext = createContext<ModelSelection>({ model: undefined, setModel: () => {} })

/** The LLM model picked in the sidebar. Pass `model` to triage/assistant hooks. */
export const useSelectedModel = () => useContext(ModelContext)
