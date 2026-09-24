import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAskAssistant } from '../api/hooks'
import { Button, Card, ErrorBox } from '../components/ui'
import { useSelectedModel } from '../model/context'

export default function AssistantPage() {
  const [params] = useSearchParams()
  const ticketId = params.get('ticket')
  const [question, setQuestion] = useState('')
  const ask = useAskAssistant()
  const { model } = useSelectedModel()

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <h1 className="text-2xl font-semibold">Assistant</h1>
      <p className="text-sm text-slate-600">
        Ask about past resolutions and services. Answers are grounded in the knowledge base and cite their sources.
        {ticketId && ' This question is scoped to the selected ticket.'}
      </p>
      <form
        className="flex flex-col gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (question.trim()) ask.mutate({ question, ticket_id: ticketId, model })
        }}
      >
        <label className="sr-only" htmlFor="assistant-question">Question</label>
        <textarea
          id="assistant-question"
          rows={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="How do we usually resolve stuck settlement confirmations?"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <div>
          <Button type="submit" disabled={ask.isPending}>{ask.isPending ? 'Thinking…' : 'Ask'}</Button>
        </div>
      </form>
      <ErrorBox error={ask.error} />
      {ask.data && (
        <>
          <Card title={`Answer · ${ask.data.model}`}>
            <p className="text-sm whitespace-pre-wrap">{ask.data.answer}</p>
          </Card>
          <Card title="Sources">
            <ul className="flex flex-col gap-2 text-sm">
              {ask.data.citations.map((c) => (
                <li key={c.ref_id}>
                  <span className="font-mono text-xs text-slate-500">[{c.ref_id}]</span> {c.title}
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
    </div>
  )
}
