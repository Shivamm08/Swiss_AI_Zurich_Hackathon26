// Friendly names for the generated contract types. Import from here in components.
import type { components, paths } from './schema'

type Schemas = components['schemas']

export type Ticket = Schemas['TicketOut']
export type TicketDetail = Schemas['TicketDetail']
export type TicketPage = Schemas['TicketPage']
export type TicketCreate = Schemas['TicketCreate']
export type EmailIngest = Schemas['EmailIngest']
export type TriageResult = Schemas['TriageResultOut']
export type Decision = Schemas['Decision']
export type DecisionEdit = Schemas['DecisionEdit']
export type ReviewCreate = Schemas['ReviewCreate']
export type Review = Schemas['ReviewOut']
export type Evidence = Schemas['Evidence']
export type KbDocument = Schemas['KbDocumentOut']
export type KbSearchRequest = Schemas['KbSearchRequest']
export type AssistantRequest = Schemas['AssistantRequest']
export type AssistantAnswer = Schemas['AssistantAnswer']
export type Metrics = Schemas['Metrics']
export type ReferenceData = Schemas['ReferenceData']
export type Health = Schemas['Health']
export type LlmModels = Schemas['LlmModels']
export type TriageRequest = Schemas['TriageRequest']
export type BatchTriageRequest = Schemas['BatchTriageRequest']

export type Level = Schemas['PriorityResponse']['priority']
export type ServiceName = Decision['service']
export type TriageState = Ticket['triage_state']
export type TicketSource = Ticket['source']
export type EvidenceKind = Evidence['kind']

export type TicketListParams = NonNullable<paths['/api/tickets']['get']['parameters']['query']>
