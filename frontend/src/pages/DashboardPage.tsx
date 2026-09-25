import {
  BookOpenCheck,
  Clock3,
  FlaskConical,
  HelpCircle,
  Route,
  Scale,
  ShieldCheck,
  Siren,
  Sparkles,
  Table2,
  Timer,
  Users,
  type LucideIcon,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { useCalibration, useDirectory, useImpact, useMetrics } from '../api/hooks'
import type { Impact } from '../api/types'
import { HBars, Legend, LineChart, StackedColumns } from '../components/charts'
import { SERIES } from '../components/styles'
import { Card, ErrorBox, Loading, PageHeader, Pill } from '../components/ui'

const pct = (v: number | null | undefined) => (v == null ? '–' : `${Math.round(v * 100)}%`)

/** 7-day rolling ratio / mean so daily noise doesn't hide the trend. */
function rolling(days: Impact['days'], pick: (d: Impact['days'][number]) => [number, number]) {
  return days.map((_, i) => {
    const win = days.slice(Math.max(0, i - 6), i + 1).map(pick)
    const [num, den] = win.reduce(([a, b], [x, y]) => [a + x, b + y], [0, 0])
    return den ? num / den : null
  })
}

function PainCard({ icon: Icon, pain, answer, value, unit }: { icon: LucideIcon; pain: string; answer: string; value: string; unit: string }) {
  return (
    <Card className="flex flex-col">
      <div className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-ai-soft text-ai"><Icon size={17} /></span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-balance">“{pain}”</p>
          <p className="mt-1 text-xs text-muted">{answer}</p>
        </div>
      </div>
      <div className="mt-auto flex items-baseline gap-2 border-t border-line pt-3">
        <span className="text-2xl font-semibold tabular">{value}</span>
        <span className="text-xs text-muted">{unit}</span>
      </div>
    </Card>
  )
}

export default function DashboardPage() {
  const [includeDemo, setIncludeDemo] = useState(true)
  const [showTable, setShowTable] = useState(false)
  const { data, isLoading, error } = useImpact(includeDemo)
  const { data: metrics } = useMetrics()
  const { data: calibration } = useCalibration()
  const { data: departments } = useDirectory()

  const series = useMemo(() => {
    if (!data) return null
    const days = data.days.map((d) => d.day)
    return {
      days,
      acceptance: rolling(data.days, (d) => [d.approved, d.approved + d.edited + d.rejected]),
      reviewTime: rolling(data.days, (d) => [(d.avg_review_seconds ?? 0) * (d.approved + d.edited + d.rejected), d.avg_review_seconds == null ? 0 : d.approved + d.edited + d.rejected]),
      routes: [
        { label: 'High confidence', color: SERIES[0], values: data.days.map((d) => d.auto) },
        { label: 'Assigned, review', color: SERIES[1], values: data.days.map((d) => d.review) },
        { label: 'Needs human triage', color: SERIES[2], values: data.days.map((d) => d.triage) },
      ],
    }
  }, [data])

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Impact"
        subtitle="The everyday pain points of a Jira service desk, and what Triage Copilot changes about each of them."
        actions={
          <label className="flex cursor-pointer items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-sm shadow-card" htmlFor="demo-toggle">
            <input id="demo-toggle" type="checkbox" checked={includeDemo} onChange={(e) => setIncludeDemo(e.target.checked)} className="accent-[var(--color-ai)]" />
            Include simulated 4-week history
          </label>
        } />
      {includeDemo && (
        <p className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-900">
          <FlaskConical size={16} className="mt-0.5 shrink-0" />
          Includes a <b className="mx-1">simulated</b> four-week desk history (generated from the training data with the real priority rules) so trends are visible.
          Untick the box to see only real tickets.
        </p>
      )}
      <ErrorBox error={error} />
      {isLoading && <Loading />}

      {data && series && (
        <>
          <section className="grid gap-4 md:grid-cols-3">
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-ink to-ink-3 p-5 text-white shadow-pop">
              <Sparkles size={80} className="absolute -right-4 -bottom-4 opacity-10" />
              <p className="text-xs tracking-wider text-slate-300 uppercase">Analyst time saved</p>
              <p className="mt-1 text-4xl font-semibold tabular">{Math.round(data.minutes_saved / 60)} h</p>
              <p className="mt-1 text-xs text-slate-400">{data.tickets_triaged} tickets × {data.manual_triage_minutes} min manual triage, minus actual review time (assumption)</p>
            </div>
            <div className="rounded-2xl border border-line bg-surface p-5 shadow-card">
              <p className="text-xs tracking-wider text-muted uppercase">Drafts accepted as proposed</p>
              <p className="mt-1 text-4xl font-semibold tabular">{pct(data.acceptance_rate)}</p>
              <p className="mt-1 text-xs text-muted">of reviewed proposals were approved without any edit</p>
            </div>
            <div className="rounded-2xl border border-line bg-surface p-5 shadow-card">
              <p className="text-xs tracking-wider text-muted uppercase">Time to a full proposal</p>
              <p className="mt-1 text-4xl font-semibold tabular">{data.avg_triage_seconds ?? '–'} s</p>
              <p className="mt-1 text-xs text-muted">then {data.avg_review_seconds ?? '–'} s of human review on average</p>
            </div>
          </section>

          <section>
            <h2 className="mb-3 text-[13px] font-semibold tracking-wide text-muted uppercase">Pain points we solve</h2>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <PainCard icon={Route} pain="Tickets bounce between teams" answer="The AI reads the content, not the intake field, and re-routes with visible reasons."
                value={String(data.misroutes_caught)} unit="misrouted tickets caught" />
              <PainCard icon={Scale} pain="Everything is marked urgent" answer="Priority comes from an auditable rule and the official matrix, never from who shouts loudest."
                value={String(data.priority_corrected)} unit="priorities corrected" />
              <PainCard icon={BookOpenCheck} pain="Fixes live in people's heads" answer="Every finished ticket becomes knowledge the next similar ticket reuses: the learning loop."
                value={String(data.learned_documents)} unit="resolved fixes now reusable" />
              <PainCard icon={Clock3} pain="Tickets wait hours for first triage" answer="A complete proposal in seconds, with SLA timers from the moment it arrives."
                value={`${data.avg_triage_seconds ?? '–'} s`} unit={`vs ~${data.manual_triage_minutes} min by hand`} />
              <PainCard icon={Users} pain="One expert gets all the tickets" answer="Assignment balances expertise with capacity, so nobody is buried."
                value={pct(data.max_load)} unit={`busiest person's load · ${data.over_capacity} over capacity`} />
              <PainCard icon={Siren} pain="Escalations get lost in email" answer="Critical tickets alert the owning team instantly; escalations carry the ticket and an AI-drafted brief."
                value={String(data.escalations)} unit="escalations with full context" />
              <PainCard icon={ShieldCheck} pain="Nobody trusts a black-box AI" answer="Every step is shown live, confidence is measured, and an analyst approves every ticket before anyone works on it."
                value={pct(data.auto_routed_share)} unit="high confidence: one-click approval" />
              <PainCard icon={HelpCircle} pain="Vague tickets: “pls fix asap”" answer="Unclear tickets are detected and the draft asks the reporter for exactly what's missing."
                value={String(data.clarifications_requested)} unit="vague tickets caught early" />
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-3">
            <Card title="Tickets triaged per day, by route" className="xl:col-span-2"
              actions={<button type="button" onClick={() => setShowTable((v) => !v)} className="inline-flex items-center gap-1 text-xs text-accent hover:underline"><Table2 size={13} />{showTable ? 'Chart' : 'Table'}</button>}>
              {showTable ? (
                <div className="max-h-56 overflow-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="text-muted"><tr><th className="py-1">Day</th>{series.routes.map((r) => <th key={r.label}>{r.label}</th>)}<th>Misroutes caught</th></tr></thead>
                    <tbody>
                      {data.days.map((d) => (
                        <tr key={d.day} className="border-t border-line tabular"><td className="py-1">{d.day}</td><td>{d.auto}</td><td>{d.review}</td><td>{d.triage}</td><td>{d.misroutes}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <>
                  <StackedColumns days={series.days} series={series.routes} />
                  <div className="mt-2"><Legend items={series.routes.map((r) => ({ label: r.label, color: r.color }))} /></div>
                </>
              )}
            </Card>
            <Card title="Does confidence mean something?">
              {calibration && (
                <HBars rows={calibration.buckets.filter((b) => b.reviewed > 0).map((b) => ({
                  label: `${Math.round(b.low * 100)}–${Math.round(b.high * 100)}% confident`,
                  value: Math.round((b.agreement ?? 0) * 100),
                  hint: `${b.reviewed} reviewed`,
                }))} format={(v) => `${v}% accepted`} />
              )}
              <p className="mt-3 text-xs text-muted">Share of reviewed proposals accepted without changing service or priority, per confidence band. Higher confidence should mean higher acceptance.</p>
            </Card>
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            <Card title="Draft acceptance rate (7-day rolling)">
              <LineChart days={series.days} values={series.acceptance} format={(v) => `${Math.round(v * 100)}%`} label="Acceptance rate" maxY={1} />
            </Card>
            <Card title="Analyst review time per ticket (7-day rolling)">
              <LineChart days={series.days} values={series.reviewTime} color={SERIES[1]} format={(v) => `${Math.round(v)} s`} label="Review time" />
            </Card>
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            <Card title="Open tickets by department">
              {departments && <HBars rows={[...departments].sort((a, b) => b.open_tickets - a.open_tickets).map((d) => ({ label: d.team, value: d.open_tickets, hint: `${d.escalations} escalations` }))} />}
            </Card>
            <Card title="What analysts corrected most" actions={<Pill className="bg-canvas text-muted"><Timer size={11} />feeds the learning loop</Pill>}>
              {metrics && Object.keys(metrics.field_override_counts).length > 0 ? (
                <HBars color={SERIES[1]} rows={Object.entries(metrics.field_override_counts).sort((a, b) => b[1] - a[1])
                  .map(([field, n]) => ({ label: field.replaceAll('_', ' '), value: n }))} />
              ) : <p className="text-sm text-muted">No edits yet.</p>}
            </Card>
          </section>
        </>
      )}
    </div>
  )
}
