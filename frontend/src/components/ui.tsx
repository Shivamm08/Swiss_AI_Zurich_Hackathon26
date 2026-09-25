// Shared UI primitives. Pages compose these; tokens live in index.css (@theme).
import { AlertTriangle, Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Level, TriageState } from '../api/types'
import { PRIORITY_STYLES } from './styles'

export function Card({ title, icon, actions, children, className = '', padded = true }: {
  title?: ReactNode
  icon?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  padded?: boolean
}) {
  return (
    <section className={`rounded-xl border border-line bg-surface shadow-card ${className}`}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-2 border-b border-line px-4 py-2.5">
          <h2 className="flex items-center gap-2 text-[13px] font-semibold tracking-wide text-ink">
            {icon && <span className="text-muted">{icon}</span>}
            {title}
          </h2>
          {actions}
        </header>
      )}
      <div className={padded ? 'p-4' : ''}>{children}</div>
    </section>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight text-balance">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'ai'

export function Button({
  children,
  variant = 'primary',
  icon,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; icon?: ReactNode }) {
  const styles: Record<ButtonVariant, string> = {
    primary: 'bg-accent text-white hover:brightness-110 shadow-sm',
    secondary: 'border border-line bg-surface text-ink hover:bg-canvas',
    danger: 'bg-red-600 text-white hover:bg-red-700 shadow-sm',
    ghost: 'text-muted hover:bg-canvas hover:text-ink',
    ai: 'bg-gradient-to-r from-ai to-accent text-white shadow-sm hover:brightness-110',
  }
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${props.className ?? ''}`}
    >
      {icon}
      {children}
    </button>
  )
}

export function Pill({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${className}`}>
      {children}
    </span>
  )
}

export function PriorityPill({ level }: { level?: string | null }) {
  if (!level) return <span className="text-muted">–</span>
  const style = PRIORITY_STYLES[level as Level]
  return (
    <Pill className={style?.pill ?? 'bg-slate-100'}>
      <span className={`h-1.5 w-1.5 rounded-full ${style?.dot ?? 'bg-slate-400'}`} />
      {level}
    </Pill>
  )
}

const STATE_STYLES: Record<TriageState, [string, string]> = {
  new: ['bg-slate-100 text-slate-700', 'new'],
  proposed: ['bg-ai-soft text-ai', 'proposed'],
  approved: ['bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200', 'approved'],
  edited: ['bg-accent-soft text-accent', 'edited'],
  rejected: ['bg-red-50 text-red-700 ring-1 ring-red-200', 'rejected'],
}

export const StatePill = ({ state }: { state: TriageState }) => <Pill className={STATE_STYLES[state][0]}>{STATE_STYLES[state][1]}</Pill>

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <p role="alert" className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      {error instanceof Error ? error.message : 'Something went wrong'}
    </p>
  )
}

export const Loading = ({ label = 'Loading…' }: { label?: string }) => (
  <p className="flex items-center gap-2 text-sm text-muted"><Loader2 size={16} className="animate-spin" />{label}</p>
)

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line bg-surface/60 px-6 py-12 text-center">
      {icon && <span className="text-muted">{icon}</span>}
      <p className="font-medium">{title}</p>
      {children && <div className="max-w-md text-sm text-muted">{children}</div>}
    </div>
  )
}

export function Field({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[8.5rem_1fr] gap-2 py-1.5 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 break-words">{children ?? '–'}</dd>
    </div>
  )
}

export const inputClass =
  'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm placeholder:text-slate-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20'
