// Copilot chat: POST /api/assistant/stream returns server-sent events
// ("sources" first, then "token" chunks, then "done").
import { useCallback, useRef, useState } from 'react'
import type { CopilotEvent, Evidence } from './types'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Evidence[]
  /** What the answer rests on: sources, the open ticket, nothing matching, or refused as off-topic. */
  grounding?: CopilotEvent['grounding']
  streaming?: boolean
  error?: boolean
  model?: string
}

let counter = 0
const nextId = () => `m${Date.now()}-${counter++}`

export function useCopilotChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [busy, setBusy] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  // Source of truth for the conversation; state mirrors it for rendering.
  const current = useRef<ChatMessage[]>([])
  const commit = (next: ChatMessage[]) => { current.current = next; setMessages(next) }
  const update = (id: string, patch: (m: ChatMessage) => Partial<ChatMessage>) =>
    commit(current.current.map((m) => (m.id === id ? { ...m, ...patch(m) } : m)))

  const send = useCallback(async (question: string, opts: { ticketId?: string | null; model?: string } = {}) => {
    const text = question.trim()
    if (!text) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const user: ChatMessage = { id: nextId(), role: 'user', content: text }
    const answer: ChatMessage = { id: nextId(), role: 'assistant', content: '', streaming: true }
    const history = [...current.current, user].filter((m) => !m.error).map(({ role, content }) => ({ role, content }))
    commit([...current.current, user, answer])
    setBusy(true)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL ?? ''}/api/assistant/stream`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ messages: history, ticket_id: opts.ticketId ?? null, model: opts.model ?? null }),
        signal: controller.signal,
      })
      if (!res.ok || !res.body) throw new Error((await res.json().catch(() => null))?.detail ?? `Request failed (${res.status})`)
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let split = buffer.indexOf('\n\n')
        while (split >= 0) {
          const line = buffer.slice(0, split).split('\n').find((l) => l.startsWith('data: '))
          buffer = buffer.slice(split + 2)
          split = buffer.indexOf('\n\n')
          if (!line) continue
          const event = JSON.parse(line.slice(6)) as CopilotEvent
          if (event.type === 'sources') update(answer.id, () => ({ citations: event.citations, grounding: event.grounding }))
          if (event.type === 'token') update(answer.id, (m) => ({ content: m.content + (event.text ?? '') }))
          if (event.type === 'done') update(answer.id, () => ({ streaming: false, model: event.model ?? undefined }))
          if (event.type === 'error') update(answer.id, () => ({ streaming: false, error: true, content: event.text ?? 'Something went wrong' }))
        }
      }
      update(answer.id, () => ({ streaming: false }))
    } catch (err) {
      if (!controller.signal.aborted) {
        update(answer.id, () => ({ streaming: false, error: true, content: err instanceof Error ? err.message : String(err) }))
      }
    } finally {
      if (abortRef.current === controller) setBusy(false)
    }
  }, [])

  const stop = () => { abortRef.current?.abort(); setBusy(false); commit(current.current.map((m) => ({ ...m, streaming: false }))) }
  const clear = () => { stop(); commit([]) }
  return { messages, busy, send, stop, clear }
}
