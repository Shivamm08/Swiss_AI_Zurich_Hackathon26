// Shared style tables (kept out of component files so fast refresh keeps working).
import type { Level } from '../api/types'

export const PRIORITY_STYLES: Record<Level, { pill: string; stripe: string; dot: string }> = {
  Highest: { pill: 'bg-red-50 text-red-700 ring-1 ring-red-200', stripe: 'bg-red-600', dot: 'bg-red-600' },
  High: { pill: 'bg-orange-50 text-orange-700 ring-1 ring-orange-200', stripe: 'bg-orange-500', dot: 'bg-orange-500' },
  Medium: { pill: 'bg-amber-50 text-amber-800 ring-1 ring-amber-200', stripe: 'bg-amber-400', dot: 'bg-amber-400' },
  Low: { pill: 'bg-sky-50 text-sky-700 ring-1 ring-sky-200', stripe: 'bg-sky-400', dot: 'bg-sky-400' },
  Lowest: { pill: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200', stripe: 'bg-slate-300', dot: 'bg-slate-400' },
}

const AVATAR_COLORS = [
  'bg-sky-100 text-sky-800', 'bg-emerald-100 text-emerald-800', 'bg-amber-100 text-amber-800',
  'bg-rose-100 text-rose-800', 'bg-violet-100 text-violet-800', 'bg-teal-100 text-teal-800',
  'bg-orange-100 text-orange-800', 'bg-indigo-100 text-indigo-800', 'bg-lime-100 text-lime-800',
]

/** Stable avatar color for a person or team name. */
export function avatarColor(key: string): string {
  let hash = 0
  for (const ch of key) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

export function initials(name: string): string {
  return name.split(/[\s.@]+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join('')
}

export const ROLE_LABEL = { admin: 'Admin', analyst: 'Team Lead / Analyst', specialist: 'Specialist' } as const

/** Chart series colors: dataviz reference slots 1-3, validated (CVD ΔE ≥ 9.2 adjacent). */
export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a'] as const
