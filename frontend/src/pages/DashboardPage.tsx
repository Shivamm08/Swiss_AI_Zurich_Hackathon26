import { useCalibration, useMetrics, useReference } from '../api/hooks'
import { Card, ErrorBox, Loading } from '../components/ui'

const pct = (v: number | null | undefined) => (v == null ? '–' : `${Math.round(v * 100)}%`)

function Kpi({ label, value, hint }: { label: string; value: string | number; hint: string }) {
  return (
    <Card>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      <p className="text-xs text-slate-400">{hint}</p>
    </Card>
  )
}

function HBar({ label, value, max, color = 'bg-blue-600' }: { label: string; value: number; max: number; color?: string }) {
  return (
    <div className="grid grid-cols-[7rem_1fr_2.5rem] items-center gap-2 text-sm">
      <span className="truncate text-slate-600">{label}</span>
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
      <header>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-slate-500">The measures the challenge asks for: draft acceptance, review time and classification quality.</p>
      </header>
      <ErrorBox error={error} />
      {isLoading && <Loading />}
      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Kpi label="Draft acceptance" value={data.reviews_total ? pct(data.acceptance_rate) : 'No reviews yet'} hint="approved without edits" />
            <Kpi label="Avg review time" value={data.avg_review_seconds == null ? '–' : `${Math.round(data.avg_review_seconds)} s`} hint="per ticket" />
            <Kpi label="Auto-routed" value={pct((data.by_route.auto ?? 0) / Math.max(1, Object.values(data.by_route).reduce((a, b) => a + b, 0)))} hint="confidence ≥ 80%" />
            <Kpi label="Escalations open" value={data.escalations_open} hint="Highest on critical services" />
            <Kpi label="SLA breaches" value={data.sla_breaches} hint="open and overdue" />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Does confidence mean something?">
              {calibration && (
                <>
                  <div className="flex h-32 items-end gap-2 border-b border-slate-200">
                    {calibration.buckets.map((b) => (
                      <div key={b.low} className="flex flex-1 flex-col items-center justify-end gap-1" title={`${b.reviewed} reviewed`}>
                        <span className="text-xs tabular-nums text-slate-600">{b.agreement == null ? '' : pct(b.agreement)}</span>
                        <span className="w-full rounded-t bg-emerald-600" style={{ height: `${(b.agreement ?? 0) * 100}px` }} />
                      </div>
                    ))}
                  </div>
                  <div className="mt-1 flex gap-2 text-xs text-slate-500">
                    {calibration.buckets.map((b) => <span key={b.low} className="flex-1 text-center">{Math.round(b.low * 100)}–{Math.round(b.high * 100)}</span>)}
                  </div>
                  <p className="mt-2 text-xs text-slate-500">Confidence bucket → share analysts accepted unchanged. {calibration.note}</p>
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
                      <HBar label={`${l} · AI`} value={data.priority_ai[l] ?? 0} max={max} color="bg-violet-600" />
                    </div>
                  )
                })}
              </div>
            </Card>

            <Card title="Fields analysts corrected most">
              {Object.keys(data.field_override_counts).length === 0 ? (
                <p className="text-sm text-slate-500">No edits yet.</p>
              ) : (
                <div className="flex flex-col gap-1">
                  {Object.entries(data.field_override_counts).sort((a, b) => b[1] - a[1]).map(([field, n]) => (
                    <HBar key={field} label={field} value={n} max={Math.max(...Object.values(data.field_override_counts))} color="bg-violet-600" />
                  ))}
                </div>
              )}
              <div className="mt-4 grid grid-cols-2 gap-1 text-sm">
                {Object.entries(data.by_state).map(([state, n]) => (
                  <div key={state} className="contents"><span className="text-slate-500">{state}</span><span className="text-right tabular-nums">{n}</span></div>
                ))}
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
