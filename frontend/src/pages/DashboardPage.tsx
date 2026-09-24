import { useBatchTriage, useMetrics } from '../api/hooks'
import { Button, Card, ErrorBox, Loading } from '../components/ui'
import { useSelectedModel } from '../model/context'

const pct = (v: number | null | undefined) => (v == null ? '-' : `${Math.round(v * 100)}%`)

export default function DashboardPage() {
  const { data, isLoading, error } = useMetrics()
  const batch = useBatchTriage()
  const { model } = useSelectedModel()

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <Button onClick={() => batch.mutate({ model })} disabled={batch.isPending}>
          {batch.isPending ? 'Triaging…' : 'Triage all new tickets'}
        </Button>
      </header>
      {batch.data && (
        <p className="text-sm text-slate-600">
          Triaged {batch.data.triaged} tickets{batch.data.failed ? `, ${batch.data.failed} failed` : ''}.
        </p>
      )}
      <ErrorBox error={error ?? batch.error} />
      {isLoading && <Loading />}
      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              ['Tickets', data.tickets_total],
              ['Draft acceptance', pct(data.acceptance_rate)],
              ['Avg review time', data.avg_review_seconds == null ? '-' : `${data.avg_review_seconds}s`],
              ['Avg AI confidence', pct(data.avg_confidence)],
            ].map(([label, value]) => (
              <Card key={label}>
                <p className="text-xs text-slate-500">{label}</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
              </Card>
            ))}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Card title="Tickets by triage state">
              <dl className="grid grid-cols-2 gap-1 text-sm">
                {Object.entries(data.by_state).map(([state, count]) => (
                  <div key={state} className="contents">
                    <dt className="text-slate-500">{state}</dt>
                    <dd className="text-right tabular-nums">{count}</dd>
                  </div>
                ))}
              </dl>
            </Card>
            <Card title="Fields analysts corrected most">
              {Object.keys(data.field_override_counts).length === 0 ? (
                <p className="text-sm text-slate-500">No edits yet.</p>
              ) : (
                <dl className="grid grid-cols-2 gap-1 text-sm">
                  {Object.entries(data.field_override_counts).map(([field, count]) => (
                    <div key={field} className="contents">
                      <dt className="font-mono text-xs">{field}</dt>
                      <dd className="text-right tabular-nums">{count}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
