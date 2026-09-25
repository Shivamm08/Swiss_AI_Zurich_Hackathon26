// Live triage walkthrough: reads the server-sent events of
// GET /api/tickets/{id}/triage/stream (one TriageStreamEvent per pipeline stage).
import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { components } from './schema'

export type TriageEvent = components['schemas']['TriageStreamEvent']

async function errorText(res: Response): Promise<string> {
  try {
    const body = await res.json()
    return typeof body?.detail === 'string' ? body.detail : JSON.stringify(body)
  } catch {
    return `Request failed with status ${res.status}`
  }
}

export function useTriageStream(ticketId: string) {
  const qc = useQueryClient()
  const [events, setEvents] = useState<TriageEvent[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const start = useCallback(
    async (model?: string) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      setEvents([])
      setError(null)
      setRunning(true)
      try {
        const query = model ? `?model=${encodeURIComponent(model)}` : ''
        const res = await fetch(`${import.meta.env.VITE_API_URL ?? ''}/api/tickets/${ticketId}/triage/stream${query}`, {
          signal: controller.signal,
        })
        if (!res.ok || !res.body) throw new Error(await errorText(res))
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
            const event = JSON.parse(line.slice(6)) as TriageEvent
            setEvents((prev) => [...prev, event])
            if (event.stage === 'error') setError(`${event.message}: ${String(event.data.detail ?? '')}`)
          }
        }
        for (const key of [['ticket'], ['tickets'], ['metrics'], ['calibration'], ['workload']]) {
          qc.invalidateQueries({ queryKey: key })
        }
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (abortRef.current === controller) setRunning(false)
      }
    },
    [ticketId, qc],
  )

  useEffect(() => () => abortRef.current?.abort(), [])
  return { events, running, error, start }
}
