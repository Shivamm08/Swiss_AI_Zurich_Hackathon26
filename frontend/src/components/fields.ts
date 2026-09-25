// How every field is produced. Shown by the (i) buttons, so nobody has to guess what the AI
// decided and what plain rules computed. Keep in sync with docs/wiki/15 and the pipeline.

export type Method = 'ai' | 'rules' | 'lookup'

export const METHOD_LABEL: Record<Method, string> = { ai: 'AI reads', rules: 'Rule', lookup: 'Lookup' }

export const METHOD_BLURB: Record<Method, string> = {
  ai: 'Read from the ticket text by the language model: 3 independent votes, answers limited to fixed options.',
  rules: 'Computed by fixed, tested rules. No AI decides this value.',
  lookup: 'Looked up in a fixed table. No AI involved.',
}

export type FieldKey =
  | 'work_type' | 'service' | 'team' | 'facts' | 'impact' | 'urgency' | 'priority' | 'priority_score'
  | 'resolution' | 'resolution_comment' | 'assignee' | 'confidence' | 'sla'

export const FIELD_METHODS: Record<FieldKey, { method: Method; how: string }> = {
  work_type: { method: 'ai', how: 'Incident or Service Request, judged from the description, not the (often misleading) title. Majority of 3 votes.' },
  service: { method: 'ai', how: 'One of the 20 catalogue services, nothing else is accepted. The model sees the service cards and their boundaries. Majority of 3 votes; service counts double in the vote score.' },
  team: { method: 'lookup', how: 'Fixed by the service: every service belongs to exactly one team in the catalogue.' },
  facts: { method: 'ai', how: 'Five observations only: who is affected, how broken, workaround, regulatory/security breach, deadline. The AI never picks a priority.' },
  impact: { method: 'rules', how: 'Rule table from the facts + whether the service is critical (e.g. critical service fully down → Highest). See "Why this priority".' },
  urgency: { method: 'rules', how: 'Rule table from the facts (workaround, outage, deadline, regulatory) + service criticality. See "Why this priority".' },
  priority: { method: 'rules', how: "The challenge's official matrix: Priority = matrix[Urgency][Impact]." },
  priority_score: { method: 'rules', how: 'Formula: position inside the priority band from severity (critical, regulatory, no workaround, outage, scope, deadline) and age. Never crosses bands.' },
  resolution: { method: 'ai', how: 'done, clarification, cannot reproduce or cancelled, read from the text. Majority of 3 votes. The specialist sets the real one when closing.' },
  resolution_comment: { method: 'ai', how: 'Drafted from the matched past fix, adapted to this ticket. Only a suggestion: the specialist writes the real closing note.' },
  assignee: { method: 'rules', how: 'Expert = author of the matched past fix. Suggestion = 0.6 × expertise + 0.4 × availability among the team\'s specialists, skipping anyone at capacity. The analyst decides.' },
  confidence: { method: 'rules', how: 'min(vote agreement, similarity to the matched past case) × warning flags (generic service, unclear input, staff disagreement).' },
  sla: { method: 'rules', how: 'Fixed deadline by priority: Highest 1 h, High 4 h, Medium 24 h, Low 3 days, Lowest 5 days.' },
}
