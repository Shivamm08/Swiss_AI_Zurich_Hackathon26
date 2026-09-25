import { useCalibration, useMetrics, useReference } from '../api/hooks'
import { AlarmClock, CheckCheck, Gauge, ShieldAlert, Timer, type LucideIcon } from 'lucide-react'
import { Card, ErrorBox, Loading, PageHeader } from '../components/ui'

const pct = (v: number | null | undefined) => (v == null ? '–' : `${Math.round(v * 100)}%`)

function Kpi({ label, value, hint, icon: Icon, tone = 'text-accent bg-accent-soft' }: { label: string; value: string | number; hint: string; icon: LucideIcon; tone?: string }) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted">{label}</p>
        <span className={`grid h-8 w-8 place-items-center rounded-lg ${tone}`}><Icon size={16} /></span>
      </div>
      <p className="mt-1 text-2xl font-semibold tabular">{value}</p>
      <p className="text-xs text-muted">{hint}</p>
    </Card>
  )
}

function HBar({ label, value, max, color = 'bg-accent' }: { label: string; value: number; max: number; color?: string }) {
  return (
    <div className="grid grid-cols-[7rem_1fr_2.5rem] items-center gap-2 text-sm">
      <span className="truncate text-muted">{label}</span>
      <span className="h-2 rounded bg-slate-100"><span className={`block h-2 rounded ${color}`} style={{ width: `${max ? (value / max) * 100 : 0}%` }} /></span>
      <span className="text-right tabular-nums">{value}</span>
    </div>
  )
}

export default function DashboardPage() {
  const { data, isLoading, error } = useMetrics()
  const { data: calibration } = useCalibration()
  const { data: reference } = useReference()
  const levels = reference?.levels ?? []

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Dashboard" subtitle="The measures the challenge asks for: draft acceptance, review time and classification quality." />
      <ErrorBox error={error} />
      {isLoading && <Loading />}
      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Kpi label="Draft acceptance" icon={CheckCheck} tone="text-emerald-700 bg-emerald-50" value={data.reviews_total ? pct(data.acceptance_rate) : 'No reviews yet'} hint="approved without edits" />
            <Kpi label="Avg review time" icon={Timer} value={data.avg_review_seconds == null ? '–' : `${Math.round(data.avg_review_seconds)} s`} hint="per ticket" />
            <Kpi label="Auto-routed" icon={Gauge} tone="text-ai bg-ai-soft" value={pct((data.by_route.auto ?? 0) / Math.max(1, Object.values(data.by_route).reduce((a, b) => a + b, 0)))} hint="confidence ≥ 80%" />
            <Kpi label="Escalations open" icon={ShieldAlert} tone="text-red-700 bg-red-50" value={data.escalations_open} hint="Highest on critical services" />
            <Kpi label="SLA breaches" icon={AlarmClock} tone="text-amber-800 bg-amber-50" value={data.sla_breaches} hint="open and overdue" />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Does confidence mean something?">
              {calibration && (
                <>
                  <div className="flex h-32 items-end gap-2 border-b border-line">
                    {calibration.buckets.map((b) => (
                      <div key={b.low} className="flex flex-1 flex-col items-center justify-end gap-1" title={`${b.reviewed} reviewed`}>
                        <span className="text-xs tabular-nums text-muted">{b.agreement == null ? '' : pct(b.agreement)}</span>
                        <span className="w-full rounded-t bg-gradient-to-t from-emerald-600 to-emerald-400" style={{ height: `${(b.agreement ?? 0) * 100}px` }} />
                      </div>
                    ))}
                  </div>
                  <div className="mt-1 flex gap-2 text-xs text-muted">
                    {calibration.buckets.map((b) => <span key={b.low} className="flex-1 text-center">{Math.round(b.low * 100)}–{Math.round(b.high * 100)}</span>)}
                  </div>
                  <p className="mt-2 text-xs text-muted">Confidence bucket → share analysts accepted unchanged. {calibration.note}</p>
                </>
              )}
            </Card>

            <Card title="Priority: as submitted vs after triage">
              <div className="flex flex-col gap-1">
                {levels.map((l) => {
                  const max = Math.max(1, ...Object.values(data.priority_intake), ...Object.values(data.priority_ai))
                  return (
                    <div key={l} className="flex flex-col gap-0.5">
                      <HBar label={`${l} · intake`} value={data.priority_intake[l] ?? 0} max={max} color="bg-slate-400" />
                      <HBar label={`${l} · AI`} value={data.priority_ai[l] ?? 0} max={max} color="bg-ai" />
                    </div>
                  )
                })}
              </div>
            </Card>

            <Card title="Fields analysts corrected most">
              {Object.keys(data.field_override_counts).length === 0 ? (
                <p className="text-sm text-muted">No edits yet.</p>
              ) : (
                <div className="flex flex-col gap-1">
                  {Object.entries(data.field_override_counts).sort((a, b) => b[1] - a[1]).map(([field, n]) => (
                    <HBar key={field} label={field} value={n} max={Math.max(...Object.values(data.field_override_counts))} color="bg-ai" />
                  ))}
                </div>
              )}
              <div className="mt-4 grid grid-cols-2 gap-1 text-sm">
                {Object.entries(data.by_state).map(([state, n]) => (
                  <div key={state} className="contents"><span className="text-muted">{state}</span><span className="text-right tabular-nums">{n}</span></div>
                ))}
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
