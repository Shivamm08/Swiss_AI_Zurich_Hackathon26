// Slide-in Copilot chat: streaming answers grounded in the knowledge base, with cited sources.
import { ArrowUp, BookOpen, RotateCcw, Sparkles, Square, Ticket, X } from 'lucide-react'
import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import type { ChatMessage } from '../api/copilot'
import type { Evidence } from '../api/types'
import { Avatar } from '../components/people'
import { Pill } from '../components/ui'
import { useSelectedModel } from '../model/context'
import { useViewer } from '../viewas/context'
import type { TicketRef } from './context'

const GENERAL_PROMPTS = [
  'How do we usually fix rejected broker allocations?',
  'Which services are critical, and why does that matter?',
  'How does the system decide a ticket’s priority?',
  'What does the Rimes Data Feed service cover?',
]
const TICKET_PROMPTS = [
  'Summarise this ticket in two sentences',
  'What is the most likely fix?',
  'Who has solved something like this before?',
  'Draft a reply asking the reporter for missing details',
]

const KIND_STYLE: Record<Evidence['kind'], string> = {
  playbook: 'bg-accent-soft text-accent',
  service_card: 'bg-slate-100 text-slate-700',
  historical_ticket: 'bg-ai-soft text-ai',
}

function Inline({ text, citations, onCite }: { text: string; citations: Evidence[]; onCite: (ref: string) => void }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[A-Za-z0-9_-]+\])/g)
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>
        if (part.startsWith('`') && part.endsWith('`')) return <code key={i} className="rounded bg-canvas px-1 font-mono text-[12px]">{part.slice(1, -1)}</code>
        const ref = part.match(/^\[([A-Za-z0-9_-]+)\]$/)?.[1]
        if (ref && citations.some((c) => c.ref_id === ref)) {
          const kind = citations.find((c) => c.ref_id === ref)!.kind
          return (
            <button key={i} type="button" onClick={() => onCite(ref)}
              className={`mx-0.5 inline-flex items-center rounded px-1 align-baseline font-mono text-[10px] leading-4 ${KIND_STYLE[kind]} hover:brightness-95`}>
              {ref}
            </button>
          )
        }
        return <Fragment key={i}>{part}</Fragment>
      })}
    </>
  )
}

/** Minimal rich text: paragraphs, bullet/numbered lists, **bold**, `code`, [ref] citations. */
function RichText({ text, citations, onCite }: { text: string; citations: Evidence[]; onCite: (ref: string) => void }) {
  const blocks: ReactNode[] = []
  let list: string[] = []
  const flush = () => {
    if (list.length) {
      blocks.push(<ul key={blocks.length} className="my-1 flex list-disc flex-col gap-1 pl-5">{list.map((l, i) => <li key={i}><Inline text={l} citations={citations} onCite={onCite} /></li>)}</ul>)
      list = []
    }
  }
  for (const line of text.split('\n')) {
    const item = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/)
    if (item) { list.push(item[1]); continue }
    flush()
    if (line.trim()) blocks.push(<p key={blocks.length}><Inline text={line.replace(/^#+\s*/, '')} citations={citations} onCite={onCite} /></p>)
  }
  flush()
  return <div className="flex flex-col gap-2">{blocks}</div>
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1" aria-label="Copilot is typing">
      {[0, 1, 2].map((i) => <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted" style={{ animationDelay: `${i * 120}ms` }} />)}
    </span>
  )
}

function Bubble({ message }: { message: ChatMessage }) {
  const [openRef, setOpenRef] = useState<string | null>(null)
  const citations = message.citations ?? []
  const shown = citations.find((c) => c.ref_id === openRef)
  if (message.role === 'user') {
    return (
      <div className="animate-rise flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-md bg-accent px-3.5 py-2 text-sm whitespace-pre-wrap text-white shadow-sm">{message.content}</p>
      </div>
    )
  }
  return (
    <div className="animate-rise flex gap-2.5">
      <Avatar name="Copilot" bot size="sm" />
      <div className="min-w-0 flex-1">
        <div className={`rounded-2xl rounded-tl-md px-3.5 py-2.5 text-sm leading-relaxed ${message.error ? 'bg-red-50 text-red-800' : 'bg-canvas'}`}>
          {message.content ? (
            <>
              <RichText text={message.content} citations={citations} onCite={(r) => setOpenRef(openRef === r ? null : r)} />
              {message.streaming && <span className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 animate-pulse bg-ai" />}
            </>
          ) : message.streaming ? <TypingDots /> : null}
        </div>
        {citations.length > 0 && !message.error && (
          <div className="mt-1.5 flex flex-wrap items-center gap-1">
            <span className="flex items-center gap-1 text-[11px] text-muted"><BookOpen size={11} />Sources</span>
            {citations.map((c) => (
              <button key={c.ref_id} type="button" onClick={() => setOpenRef(openRef === c.ref_id ? null : c.ref_id)}
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium transition ${KIND_STYLE[c.kind]} ${openRef === c.ref_id ? 'ring-1 ring-current' : ''}`}
                title={c.title}>
                {c.kind === 'historical_ticket' ? 'learned' : c.kind === 'service_card' ? 'service' : 'playbook'} · {c.title.split(':')[0]}
              </button>
            ))}
          </div>
        )}
        {shown && (
          <div className="animate-rise mt-1.5 rounded-lg border border-line bg-surface p-2.5 text-xs">
            <p className="font-medium">{shown.title}</p>
            <p className="mt-1 text-muted">{shown.snippet}</p>
          </div>
        )}
        {message.model && !message.streaming && <p className="mt-1 text-[10px] text-muted">{message.model}</p>}
      </div>
    </div>
  )
}

export default function CopilotPanel({ open, onClose, messages, busy, onSend, onStop, onClear, ticket, onClearTicket }: {
  open: boolean
  onClose: () => void
  messages: ChatMessage[]
  busy: boolean
  onSend: (text: string) => void
  onStop: () => void
  onClear: () => void
  ticket: TicketRef | null
  onClearTicket: () => void
}) {
  const { user } = useViewer()
  const { model } = useSelectedModel()
  const [draft, setDraft] = useState('')
  const scroller = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)

  useEffect(() => { scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' }) }, [messages])
  useEffect(() => { if (open) setTimeout(() => input.current?.focus(), 50) }, [open])

  const submit = () => {
    if (!draft.trim() || busy) return
    onSend(draft)
    setDraft('')
  }
  const prompts = ticket ? TICKET_PROMPTS : GENERAL_PROMPTS

  return (
    <aside aria-label="Copilot" aria-hidden={!open}
      className={`fixed inset-y-0 right-0 z-40 flex w-full max-w-md flex-col border-l border-line bg-surface shadow-pop transition-transform duration-300 ${open ? 'translate-x-0' : 'pointer-events-none translate-x-full'}`}>
      <header className="flex items-center gap-3 border-b border-line bg-gradient-to-r from-ai-soft/70 to-accent-soft/60 px-4 py-3">
        <Avatar name="Copilot" bot size="md" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">Triage Copilot</p>
          <p className="truncate text-xs text-muted">Answers from your knowledge base · {model ?? 'default model'}</p>
        </div>
        <button type="button" onClick={onClear} className="rounded-lg p-1.5 text-muted hover:bg-surface/70" title="New conversation"><RotateCcw size={16} /></button>
        <button type="button" onClick={onClose} className="rounded-lg p-1.5 text-muted hover:bg-surface/70" title="Close (Esc)"><X size={18} /></button>
      </header>

      {ticket && (
        <div className="flex items-center gap-2 border-b border-line bg-accent-soft/40 px-4 py-2 text-xs">
          <Ticket size={13} className="text-accent" />
          <span className="min-w-0 flex-1 truncate"><b>#{ticket.number}</b> in context · {ticket.summary}</span>
          <button type="button" onClick={onClearTicket} className="text-muted hover:text-ink" aria-label="Remove ticket context"><X size={13} /></button>
        </div>
      )}

      <div ref={scroller} className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col justify-end gap-4 pb-2">
            <div>
              <span className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-ai to-accent text-white shadow-pop"><Sparkles size={20} /></span>
              <p className="mt-3 text-lg font-semibold">Hi {user?.name.split(' ')[0] ?? 'there'}, how can I help?</p>
              <p className="text-sm text-muted">I search the service catalogue, the resolution playbook and every ticket your team resolved, and I cite where each answer comes from.</p>
            </div>
            <div className="flex flex-col gap-2">
              {prompts.map((p) => (
                <button key={p} type="button" onClick={() => onSend(p)}
                  className="rounded-xl border border-line px-3 py-2 text-left text-sm transition hover:border-ai/40 hover:bg-ai-soft/40">{p}</button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">{messages.map((m) => <Bubble key={m.id} message={m} />)}</div>
        )}
      </div>

      <form className="border-t border-line p-3" onSubmit={(e) => { e.preventDefault(); submit() }}>
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-canvas px-3 py-2 focus-within:border-ai/50 focus-within:ring-2 focus-within:ring-ai/10">
          <label className="sr-only" htmlFor="copilot-input">Message Copilot</label>
          <textarea id="copilot-input" ref={input} rows={1} value={draft} placeholder={ticket ? `Ask about #${ticket.number}…` : 'Ask anything about tickets, services or fixes…'}
            onChange={(e) => { setDraft(e.target.value); e.target.style.height = 'auto'; e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px` }}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
            className="max-h-36 min-h-6 flex-1 resize-none bg-transparent text-sm focus:outline-none" />
          {busy ? (
            <button type="button" onClick={onStop} className="grid h-8 w-8 place-items-center rounded-full bg-ink text-white" title="Stop"><Square size={12} /></button>
          ) : (
            <button type="submit" disabled={!draft.trim()} className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-ai to-accent text-white transition disabled:opacity-40" title="Send (Enter)"><ArrowUp size={16} /></button>
          )}
        </div>
        <p className="mt-1.5 flex items-center justify-between px-1 text-[10px] text-muted">
          <span>Enter to send · Shift+Enter for a new line</span>
          <Pill className="bg-transparent px-0 text-[10px] text-muted">AI can make mistakes: check the sources</Pill>
        </p>
      </form>
    </aside>
  )
}
