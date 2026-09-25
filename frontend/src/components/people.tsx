import { Bot } from 'lucide-react'
import { avatarColor, initials } from './styles'

const SIZES = { xs: 'h-6 w-6 text-[10px]', sm: 'h-8 w-8 text-xs', md: 'h-10 w-10 text-sm', lg: 'h-12 w-12 text-base' }

export function Avatar({ name, email, size = 'sm', bot = false }: { name: string; email?: string; size?: keyof typeof SIZES; bot?: boolean }) {
  if (bot) {
    return (
      <span className={`grid shrink-0 place-items-center rounded-full bg-gradient-to-br from-ai to-accent text-white ${SIZES[size]}`}>
        <Bot size={size === 'xs' ? 12 : 16} />
      </span>
    )
  }
  return (
    <span className={`grid shrink-0 place-items-center rounded-full font-semibold ${avatarColor(email ?? name)} ${SIZES[size]}`} title={name}>
      {initials(name)}
    </span>
  )
}

export function AvatarStack({ people, max = 4 }: { people: { name: string; email: string }[]; max?: number }) {
  const shown = people.slice(0, max)
  return (
    <span className="flex -space-x-1">
      {shown.map((p) => <span key={p.email} className="rounded-full ring-2 ring-surface"><Avatar name={p.name} email={p.email} size="xs" /></span>)}
      {people.length > max && (
        <span className="grid h-6 w-6 place-items-center rounded-full bg-canvas text-[10px] font-semibold text-muted ring-2 ring-surface">+{people.length - max}</span>
      )}
    </span>
  )
}

export function LoadBar({ open, capacity }: { open: number; capacity: number }) {
  const load = capacity ? open / capacity : 0
  return (
    <span className="inline-flex items-center gap-1.5 text-xs tabular" title={`${open} open of ${capacity}`}>
      <span className="inline-block h-1.5 w-12 overflow-hidden rounded bg-slate-200">
        <span className={`block h-1.5 ${load >= 1 ? 'bg-red-500' : load >= 0.6 ? 'bg-amber-400' : 'bg-emerald-500'}`} style={{ width: `${Math.min(100, load * 100)}%` }} />
      </span>
      {open}/{capacity}
    </span>
  )
}
