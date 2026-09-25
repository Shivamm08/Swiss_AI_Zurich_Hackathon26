import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchSubmission, useBatchTriage, useImportTickets, useIngestEmail, useTickets } from '../api/hooks'
import type { TicketSource } from '../api/types'
import { Button, Card, ErrorBox, PageHeader } from '../components/ui'
import { useSelectedModel } from '../model/context'

const input = 'rounded-md border border-line px-2 py-1 text-sm'

function BatchTriageCard() {
  const { model } = useSelectedModel()
  const batch = useBatchTriage()
  const { data: pending } = useTickets({ state: 'new', limit: 1 })
  return (
    <Card title="Batch triage (silent)">
      <p className="mb-3 text-sm text-muted">
        Triages every new ticket in the background, without the live walkthrough. For the demo, open tickets one by one from the Queue instead.
      </p>
      <Button onClick={() => batch.mutate({ model })} disabled={batch.isPending || !pending?.total}>
        {batch.isPending ? 'Triaging…' : `Triage ${pending?.total ?? 0} new tickets`}
      </Button>
      {batch.data && <p className="mt-2 text-sm text-muted">Triaged {batch.data.triaged}{batch.data.failed ? `, ${batch.data.failed} failed` : ''}.</p>}
      <ErrorBox error={batch.error} />
    </Card>
  )
}

export default function ImportPage() {
  const navigate = useNavigate()
  const importTickets = useImportTickets()
  const ingestEmail = useIngestEmail()
  const [file, setFile] = useState<File | null>(null)
  const [source, setSource] = useState<TicketSource>('challenge')
  const [email, setEmail] = useState({ from_address: '', subject: '', body: '' })
  const [exportError, setExportError] = useState<unknown>(null)

  const downloadSubmission = async () => {
    setExportError(null)
    try {
      const records = await fetchSubmission('challenge')
      const url = URL.createObjectURL(new Blob([JSON.stringify(records, null, 2)], { type: 'application/json' }))
      const a = Object.assign(document.createElement('a'), { href: url, download: 'submission.json' })
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setExportError(err)
    }
  }

  return (
    <div className="flex max-w-3xl flex-col gap-5">
      <PageHeader title="Intake & export" subtitle="Bring tickets in, run silent batch triage, and export the challenge submission." />
      <BatchTriageCard />

      <Card title="Import a Jira export (JSON)">
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (file) importTickets.mutate({ file, source })
          }}
        >
          <label className="flex flex-col gap-1 text-sm" htmlFor="import-file">
            File
            <input id="import-file" type="file" accept="application/json" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          <label className="flex flex-col gap-1 text-sm" htmlFor="import-source">
            Source
            <select id="import-source" value={source} onChange={(e) => setSource(e.target.value as TicketSource)} className={input}>
              <option value="challenge">challenge</option>
              <option value="training">training</option>
            </select>
          </label>
          <Button type="submit" disabled={!file || importTickets.isPending}>Import</Button>
        </form>
        {importTickets.data && (
          <p className="mt-2 text-sm text-muted">
            Imported {importTickets.data.imported}, skipped {importTickets.data.skipped}.
          </p>
        )}
        <ErrorBox error={importTickets.error} />
      </Card>

      <Card title="Paste an incoming email">
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            ingestEmail.mutate(email, { onSuccess: (t) => navigate(`/tickets/${t.id}`) })
          }}
        >
          <label className="flex flex-col gap-1 text-sm" htmlFor="email-from">
            From
            <input id="email-from" required value={email.from_address} onChange={(e) => setEmail({ ...email, from_address: e.target.value })} className={input} />
          </label>
          <label className="flex flex-col gap-1 text-sm" htmlFor="email-subject">
            Subject
            <input id="email-subject" required value={email.subject} onChange={(e) => setEmail({ ...email, subject: e.target.value })} className={input} />
          </label>
          <label className="flex flex-col gap-1 text-sm" htmlFor="email-body">
            Body
            <textarea id="email-body" required rows={5} value={email.body} onChange={(e) => setEmail({ ...email, body: e.target.value })} className={input} />
          </label>
          <div>
            <Button type="submit" disabled={ingestEmail.isPending}>Create ticket</Button>
          </div>
        </form>
        <ErrorBox error={ingestEmail.error} />
      </Card>

      <Card title="Export challenge submission">
        <p className="mb-2 text-sm text-muted">
          Challenge-format JSON using the analyst's decision where reviewed, otherwise the latest AI proposal.
        </p>
        <Button onClick={downloadSubmission}>Download submission.json</Button>
        <ErrorBox error={exportError} />
      </Card>
    </div>
  )
}
