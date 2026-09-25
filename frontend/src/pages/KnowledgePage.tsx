import { useState } from 'react'
import { useKbDocuments, useKbSearch, useSyncKb } from '../api/hooks'
import type { EvidenceKind } from '../api/types'
import { Button, Card, ErrorBox, Loading, Pill } from '../components/ui'

const KINDS: { value: EvidenceKind | undefined; label: string }[] = [
  { value: undefined, label: 'All' },
  { value: 'service_card', label: 'Service cards' },
  { value: 'playbook', label: 'Playbook' },
  { value: 'historical_ticket', label: 'Learned (approved tickets)' },
]

export default function KnowledgePage() {
  const [kind, setKind] = useState<EvidenceKind | undefined>()
  const [query, setQuery] = useState('')
  const docs = useKbDocuments(kind)
  const search = useKbSearch()
  const sync = useSyncKb()

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Knowledge base</h1>
        <Button variant="secondary" onClick={() => sync.mutate()} disabled={sync.isPending}>
          {sync.isPending ? 'Syncing…' : 'Re-sync from files'}
        </Button>
      </header>
      {sync.data && <p className="text-sm text-slate-600">Synced {sync.data.synced} documents, embedded {sync.data.embedded}.</p>}

      <Card title="Test retrieval">
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (query.trim()) search.mutate({ query, k: 5 })
          }}
        >
          <label className="sr-only" htmlFor="kb-query">Search the knowledge base</label>
          <input
            id="kb-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. allocations rejected by broker"
            className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          />
          <Button type="submit" disabled={search.isPending}>Search</Button>
        </form>
        <ErrorBox error={search.error} />
        {search.data && (
          <ol className="mt-3 flex flex-col gap-2 text-sm">
            {search.data.map((hit) => (
              <li key={hit.ref_id}>
                <span className="font-mono text-xs text-slate-500">{hit.kind} · {hit.ref_id} · {hit.score.toFixed(2)}</span>
                <p>{hit.snippet}</p>
              </li>
            ))}
          </ol>
        )}
      </Card>

      <div className="flex flex-wrap gap-1">
        {KINDS.map((k) => (
          <Button key={k.label} variant={kind === k.value ? 'primary' : 'secondary'} onClick={() => setKind(k.value)}>
            {k.label}
          </Button>
        ))}
      </div>
      <ErrorBox error={docs.error} />
      {docs.isLoading && <Loading />}
      <div className="grid gap-3 md:grid-cols-2">
        {docs.data?.map((d) => (
          <Card key={d.id}>
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <Pill className="bg-slate-100 text-slate-700">{d.kind}</Pill>
              {d.has_embedding && <Pill className="bg-violet-100 text-violet-800">embedded</Pill>}
            </div>
            <h3 className="text-sm font-semibold">{d.title}</h3>
            <p className="mt-1 text-sm text-slate-600">{d.content}</p>
          </Card>
        ))}
      </div>
    </div>
  )
}
