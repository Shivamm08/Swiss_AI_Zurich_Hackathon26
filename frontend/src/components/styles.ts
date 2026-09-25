// Shared style tables (kept out of component files so fast refresh keeps working).
import type { Level } from '../api/types'

export const PRIORITY_STYLES: Record<Level, { pill: string; stripe: string; dot: string }> = {
  Highest: { pill: 'bg-red-50 text-red-700 ring-1 ring-red-200', stripe: 'bg-red-600', dot: 'bg-red-600' },
  High: { pill: 'bg-orange-50 text-orange-700 ring-1 ring-orange-200', stripe: 'bg-orange-500', dot: 'bg-orange-500' },
  Medium: { pill: 'bg-amber-50 text-amber-800 ring-1 ring-amber-200', stripe: 'bg-amber-400', dot: 'bg-amber-400' },
  Low: { pill: 'bg-sky-50 text-sky-700 ring-1 ring-sky-200', stripe: 'bg-sky-400', dot: 'bg-sky-400' },
  Lowest: { pill: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200', stripe: 'bg-slate-300', dot: 'bg-slate-400' },
}
