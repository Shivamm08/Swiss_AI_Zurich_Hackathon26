import { ArrowRightLeft, CircleCheck, Hash, RotateCcw, MessageSquarePlus, Search, Send, Siren, Ticket as TicketIcon } from 'lucide-react'
import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useChannels, useMessages, useSendMessage, useUsers } from '../api/hooks'
import type { Channel, Message } from '../api/types'
import { Avatar, AvatarStack } from '../components/people'
import { EmptyState, ErrorBox, Pill } from '../components/ui'
import { useViewer } from '../viewas/context'

export interface ComposeState { draft?: string; ticketId?: string; kind?: Message['kind'] }

const dmChannel = (a: string, b: string) => `dm:${[a.toLowerCase(), b.toLowerCase()].sort().join('|')}`
const time = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
const dayLabel = (iso: string) => {
  const d = new Date(iso)
  const today = new Date()
  const diff = Math.round((new Date(today.toDateString()).getTime() - new Date(d.toDateString()).getTime()) / 86_400_000)
  return diff === 0 ? 'Today' : diff === 1 ? 'Yesterday' : d.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'short' })
}

function ChannelRow({ channel, active, onClick, me }: { channel: Channel; active: boolean; onClick: () => void; me?: string }) {
  const last = channel.last_message
  return (
    <button type="button" onClick={onClick}
      className={`flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left transition ${active ? 'bg-accent-soft' : 'hover:bg-canvas'}`}>
      {channel.kind === 'team'
        ? <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-ink text-white"><Hash size={15} /></span>
        : <Avatar name={channel.title} email={channel.members.find((m) => m !== me)} size="sm" />}
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span className={`truncate text-sm ${active ? 'font-semibold text-accent' : 'font-medium'}`}>{channel.title}</span>
          {last && <span className="shrink-0 text-[10px] text-muted">{time(last.created_at)}</span>}
        </span>
        <span className="block truncate text-xs text-muted">
          {last ? `${last.sender === me ? 'You' : last.sender_name.split(' ')[0]}: ${last.body}` : channel.subtitle}
        </span>
      </span>
    </button>
  )
}

function MessageItem({ m, mine }: { m: Message; mine: boolean }) {
  const ticketCard = m.ticket_id && (
    <Link to={`/tickets/${m.ticket_id}`} className="mt-2 flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-xs text-ink hover:border-accent/40">
      <TicketIcon size={14} className="text-accent" />
      <span className="font-mono text-muted">#{m.ticket_number}</span>
      <span className="min-w-0 flex-1 truncate font-medium">{m.ticket_summary}</span>
      <span className="text-accent">Open →</span>
    </Link>
  )
  if (m.kind === 'system' || (m.kind === 'escalation' && m.sender === 'triage-copilot')) {
    return (
      <div className="animate-rise mx-auto w-full max-w-2xl rounded-xl border border-red-200 bg-red-50/70 px-4 py-3 text-sm">
        <p className="mb-1 flex items-center gap-2 text-xs font-semibold text-red-700"><Siren size={14} />Automatic escalation · {time(m.created_at)}</p>
        <p className="text-red-900">{m.body}</p>
        {ticketCard}
      </div>
    )
  }
  const tag = m.kind === 'escalation'
    ? <Pill className="bg-red-50 text-red-700 ring-1 ring-red-200"><Siren size={11} />escalation</Pill>
    : m.kind === 'handoff' ? <Pill className="bg-ai-soft text-ai"><ArrowRightLeft size={11} />handed back</Pill>
    : m.kind === 'resolved' ? <Pill className="bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"><CircleCheck size={11} />ticket done · open it to reopen</Pill>
    : m.kind === 'reopened' ? <Pill className="bg-amber-50 text-amber-800 ring-1 ring-amber-200"><RotateCcw size={11} />reopened</Pill> : null
  return (
    <div className={`animate-rise flex gap-2.5 ${mine ? 'flex-row-reverse' : ''}`}>
      <Avatar name={m.sender_name} email={m.sender} size="sm" />
      <div className={`flex max-w-[75%] flex-col ${mine ? 'items-end' : 'items-start'}`}>
        <p className="mb-0.5 flex items-center gap-2 text-[11px] text-muted">
          <span className="font-medium text-ink">{mine ? 'You' : m.sender_name}</span>{time(m.created_at)}{tag}
        </p>
        <div className={`rounded-2xl px-3.5 py-2 text-sm whitespace-pre-wrap ${mine ? 'rounded-tr-md bg-accent text-white' : 'rounded-tl-md bg-surface shadow-card ring-1 ring-line'}`}>
          {m.body}
          {ticketCard}
        </div>
      </div>
    </div>
  )
}

function Composer({ channel, title, compose, onSent }: { channel: string; title: string; compose: ComposeState; onSent: () => void }) {
  const { user } = useViewer()
  const send = useSendMessage()
  const [text, setText] = useState(compose.draft ?? '')
  const submit = () => {
    if (!text.trim() || !user) return
    send.mutate(
      { channel, sender: user.email, body: text, kind: compose.kind ?? 'message', ticket_id: compose.ticketId ?? null },
      { onSuccess: () => { setText(''); onSent() } },
    )
  }
  return (
    <form className="border-t border-line bg-surface p-3" onSubmit={(e) => { e.preventDefault(); submit() }}>
      {compose.ticketId && (
        <p className="mb-2 flex items-center gap-2 text-xs text-muted">
          <TicketIcon size={13} className="text-accent" />Ticket attached{compose.kind && compose.kind !== 'message' && <Pill className="bg-red-50 text-red-700">{compose.kind}</Pill>}
          <span className="text-ai">· drafted by Copilot, edit before sending</span>
        </p>
      )}
      <div className="flex items-end gap-2 rounded-2xl border border-line bg-canvas px-3 py-2 focus-within:border-accent/50">
        <label className="sr-only" htmlFor="chat-input">Message</label>
        <textarea id="chat-input" rows={compose.draft ? 5 : 1} value={text} onChange={(e) => setText(e.target.value)} placeholder={`Message ${title}`}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
          className="max-h-40 min-h-6 flex-1 resize-none bg-transparent text-sm focus:outline-none" />
        <button type="submit" disabled={!text.trim() || send.isPending} className="grid h-8 w-8 place-items-center rounded-full bg-accent text-white disabled:opacity-40" title="Send">
          <Send size={14} />
        </button>
      </div>
      <ErrorBox error={send.error} />
    </form>
  )
}

export default function MessagesPage() {
  const { user } = useViewer()
  const me = user?.email
  const [params, setParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const compose = (location.state ?? {}) as ComposeState
  const { data: channels } = useChannels(me)
  const { data: users } = useUsers()
  const active = params.get('channel') ?? channels?.[0]?.id
  const { data: messages, error } = useMessages(active)
  const [q, setQ] = useState('')
  const [picking, setPicking] = useState(false)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages?.length, active])

  const current = channels?.find((c) => c.id === active)
  const title = current?.title ?? (active?.startsWith('dm:') ? users?.find((u) => active.includes(u.email) && u.email !== me)?.name : active?.slice(5))
  const filtered = (kind: Channel['kind']) => (channels ?? []).filter((c) => c.kind === kind && (!q || c.title.toLowerCase().includes(q.toLowerCase())))
  const memberUsers = useMemo(() => (users ?? []).filter((u) => current?.members.includes(u.email)), [users, current])

  let lastDay = ''
  return (
    <div className="-m-4 flex h-[calc(100vh-57px)] md:-m-6">
      {/* channel list */}
      <aside className="flex w-80 shrink-0 flex-col border-r border-line bg-surface">
        <div className="flex items-center justify-between px-4 pt-4 pb-2">
          <h1 className="text-lg font-semibold">Messages</h1>
          <button type="button" onClick={() => setPicking((v) => !v)} className="rounded-lg p-1.5 text-accent hover:bg-accent-soft" title="New direct message">
            <MessageSquarePlus size={18} />
          </button>
        </div>
        <label className="relative mx-4 mb-2 block" htmlFor="chat-search">
          <span className="sr-only">Search</span>
          <Search size={14} className="pointer-events-none absolute top-2.5 left-2.5 text-muted" />
          <input id="chat-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search conversations"
            className="w-full rounded-lg border border-line bg-canvas py-1.5 pr-3 pl-8 text-sm focus:border-accent focus:outline-none" />
        </label>
        {picking && (
          <div className="mx-4 mb-2 max-h-56 overflow-y-auto rounded-lg border border-line bg-surface p-1 shadow-card">
            {(users ?? []).filter((u) => u.email !== me).map((u) => (
              <button key={u.email} type="button" onClick={() => { setPicking(false); setParams({ channel: dmChannel(me!, u.email) }) }}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-canvas">
                <Avatar name={u.name} email={u.email} size="xs" />{u.name}<span className="ml-auto text-[11px] text-muted">{u.teams[0] ?? u.role}</span>
              </button>
            ))}
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-2 pb-4">
          <p className="px-2.5 pt-2 pb-1 text-[10px] font-semibold tracking-wider text-muted uppercase">Departments</p>
          {filtered('team').map((c) => <ChannelRow key={c.id} channel={c} me={me} active={c.id === active} onClick={() => setParams({ channel: c.id })} />)}
          <p className="px-2.5 pt-4 pb-1 text-[10px] font-semibold tracking-wider text-muted uppercase">Direct messages</p>
          {filtered('dm').length === 0 && <p className="px-2.5 text-xs text-muted">No direct messages yet.</p>}
          {filtered('dm').map((c) => <ChannelRow key={c.id} channel={c} me={me} active={c.id === active} onClick={() => setParams({ channel: c.id })} />)}
        </div>
      </aside>

      {/* conversation */}
      <section className="flex min-w-0 flex-1 flex-col bg-canvas">
        {!active ? <div className="p-6"><EmptyState title="Pick a conversation" /></div> : (
          <>
            <header className="flex items-center gap-3 border-b border-line bg-surface px-5 py-3">
              {active.startsWith('team:') ? <span className="grid h-9 w-9 place-items-center rounded-lg bg-ink text-white"><Hash size={16} /></span>
                : <Avatar name={title ?? '?'} email={active.slice(3).split('|').find((e) => e !== me)} size="md" />}
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{title}</p>
                <p className="truncate text-xs text-muted">{active.startsWith('team:') ? current?.subtitle : 'Direct message'}</p>
              </div>
              {memberUsers.length > 0 && <AvatarStack people={memberUsers} max={5} />}
            </header>
            <div className="flex-1 overflow-y-auto px-5 py-4">
              <ErrorBox error={error} />
              {messages?.length === 0 && <EmptyState icon={<Hash size={24} />} title="No messages yet">Say hello, or share a ticket from its page.</EmptyState>}
              <div className="flex flex-col gap-4">
                {messages?.map((m) => {
                  const day = dayLabel(m.created_at)
                  const divider = day !== lastDay
                  lastDay = day
                  return (
                    <Fragment key={m.id}>
                      {divider && <p className="my-1 text-center text-[11px] font-medium text-muted"><span className="rounded-full bg-surface px-3 py-1 ring-1 ring-line">{day}</span></p>}
                      <MessageItem m={m} mine={m.sender === me} />
                    </Fragment>
                  )
                })}
              </div>
              <div ref={bottom} />
            </div>
            <Composer key={`${active}-${location.key}`} channel={active} title={title ?? ''} compose={compose}
              onSent={() => navigate(`/messages?channel=${encodeURIComponent(active)}`, { replace: true, state: {} })} />
          </>
        )}
      </section>
    </div>
  )
}
