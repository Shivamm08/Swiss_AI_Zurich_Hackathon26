// Small shared UI primitives. Swap for a component library (e.g. shadcn/ui) later if wanted.
import type { ReactNode } from 'react'
import type { Level, TriageState } from '../api/types'

export function Card({ title, actions, children }: { title?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      {(title || actions) && (
        <header className="mb-3 flex items-center justify-between gap-2">
          {title && <h2 className="text-sm font-semibold text-slate-700">{title}</h2>}
          {actions}
        </header>
      )}
      {children}
    </section>
  )
}

export function Button({
  children,
  variant = 'primary',
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' }) {
  const styles = {
    primary: 'bg-blue-700 text-white hover:bg-blue-800',
    secondary: 'border border-slate-300 bg-white text-slate-800 hover:bg-slate-50',
    danger: 'bg-red-700 text-white hover:bg-red-800',
  }[variant]
  return (
    <button
      {...props}
      className={`rounded-md px-3 py-1.5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-blue-600 disabled:opacity-50 ${styles} ${props.className ?? ''}`}
    >
      {children}
    </button>
  )
}

const PRIORITY_STYLES: Record<Level, string> = {
  Highest: 'bg-red-100 text-red-800',
  High: 'bg-orange-100 text-orange-800',
  Medium: 'bg-amber-100 text-amber-800',
  Low: 'bg-sky-100 text-sky-800',
  Lowest: 'bg-slate-100 text-slate-700',
}

const STATE_STYLES: Record<TriageState, string> = {
  new: 'bg-slate-100 text-slate-700',
  proposed: 'bg-violet-100 text-violet-800',
  approved: 'bg-emerald-100 text-emerald-800',
  edited: 'bg-blue-100 text-blue-800',
  rejected: 'bg-red-100 text-red-800',
}

export function Pill({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>{children}</span>
}

export const PriorityPill = ({ level }: { level?: string | null }) =>
  level ? <Pill className={PRIORITY_STYLES[level as Level] ?? 'bg-slate-100'}>{level}</Pill> : <span>-</span>

export const StatePill = ({ state }: { state: TriageState }) => <Pill className={STATE_STYLES[state]}>{state}</Pill>

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
      {error instanceof Error ? error.message : 'Something went wrong'}
    </p>
  )
}

export const Loading = () => <p className="text-sm text-slate-500">Loading…</p>

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[9rem_1fr] gap-2 py-1 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="min-w-0 break-words">{children ?? '-'}</dd>
    </div>
  )
}
