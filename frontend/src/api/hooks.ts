// One React Query hook per backend endpoint. Pages only talk to the backend
// through these, so an API change surfaces here as a type error.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError, unwrap } from './client'
import type {
  AssistantRequest,
  BatchTriageRequest,
  EmailIngest,
  EvidenceKind,
  KbSearchRequest,
  DraftRequest,
  MessageCreate,
  RubricPreviewRequest,
  ReviewCreate,
  WorkUpdate,
  TicketCreate,
  TicketListParams,
  TicketSource,
  TriageRequest,
} from './types'

export const queryKeys = {
  health: ['health'] as const,
  reference: ['reference'] as const,
  llmModels: ['llm-models'] as const,
  tickets: (params: TicketListParams) => ['tickets', params] as const,
  ticket: (id: string) => ['ticket', id] as const,
  kbDocuments: (kind?: EvidenceKind) => ['kb-documents', kind ?? 'all'] as const,
  metrics: ['metrics'] as const,
  calibration: ['calibration'] as const,
  users: ['users'] as const,
  workload: (team: string) => ['workload', team] as const,
  settings: ['settings'] as const,
}

// ------------------------------------------------------------------ system

export const useHealth = () =>
  useQuery({
    queryKey: queryKeys.health,
    queryFn: () => unwrap(api.GET('/api/health')),
    refetchInterval: 30_000,
  })

export const useReference = () =>
  useQuery({
    queryKey: queryKeys.reference,
    queryFn: () => unwrap(api.GET('/api/reference')),
    staleTime: Infinity,
  })

export const useLlmModels = () =>
  useQuery({
    queryKey: queryKeys.llmModels,
    queryFn: () => unwrap(api.GET('/api/llm/models')),
    staleTime: Infinity,
  })

// ------------------------------------------------------------------ tickets

export const useTickets = (params: TicketListParams = {}) =>
  useQuery({
    queryKey: queryKeys.tickets(params),
    queryFn: () => unwrap(api.GET('/api/tickets', { params: { query: params } })),
  })

export const useTicket = (ticketId: string) =>
  useQuery({
    queryKey: queryKeys.ticket(ticketId),
    queryFn: () => unwrap(api.GET('/api/tickets/{ticket_id}', { params: { path: { ticket_id: ticketId } } })),
  })

function useInvalidateTickets() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['tickets'] })
    qc.invalidateQueries({ queryKey: ['ticket'] })
    qc.invalidateQueries({ queryKey: queryKeys.metrics })
    qc.invalidateQueries({ queryKey: queryKeys.calibration })
    qc.invalidateQueries({ queryKey: ['workload'] })
    qc.invalidateQueries({ queryKey: ['kb-documents'] })
  }
}

export const useCreateTicket = () => {
  const invalidate = useInvalidateTickets()
  return useMutation({
    mutationFn: (body: TicketCreate) => unwrap(api.POST('/api/tickets', { body })),
    onSuccess: invalidate,
  })
}

export const useIngestEmail = () => {
  const invalidate = useInvalidateTickets()
  return useMutation({
    mutationFn: (body: EmailIngest) => unwrap(api.POST('/api/tickets/from-email', { body })),
    onSuccess: invalidate,
  })
}

export const useImportTickets = () => {
  const invalidate = useInvalidateTickets()
  return useMutation({
    mutationFn: ({ file, source }: { file: File; source: TicketSource }) =>
      unwrap(
        api.POST('/api/tickets/import', {
          body: { file: file as unknown as string, source },
          bodySerializer: () => {
            const form = new FormData()
            form.append('file', file)
            form.append('source', source)
            return form
          },
        }),
      ),
    onSuccess: invalidate,
  })
}

export const useDeleteTicket = () => {
  const invalidate = useInvalidateTickets()
  return useMutation({
    mutationFn: async (ticketId: string) => {
      const { response, error } = await api.DELETE('/api/tickets/{ticket_id}', {
        params: { path: { ticket_id: ticketId } },
      })
      if (!response.ok) throw new ApiError(response.status, error)
    },
    onSuccess: invalidate,
  })
}

// ------------------------------------------------------------------ triage + review

export const useTriageTicket = () => {
  const invalidate = useInvalidateTickets()
  return useMutation({
    mutationFn: ({ ticketId, model }: { ticketId: string } & TriageRequest) =>
      unwrap(
        api.POST('/api/tickets/{ticket_id}/triage', { params: { path: { ticket_id: ticketId } }, body: { model } }),
      ),
    onSuccess: invalidate,
  })
}

export const useBatchTriage = () => {
  const invalidate = useInvalidateTickets()
  return useMutation({
    mutationFn: (body: BatchTriageRequest = {}) =>
      unwrap(api.POST('/api/triage/batch', { body })),
    onSuccess: invalidate,
  })
}

export const useReviewTriage = () => {
  const invalidate = useInvalidateTickets()
  return useMutation({
    mutationFn: ({ resultId, body }: { resultId: string; body: ReviewCreate }) =>
      unwrap(api.POST('/api/triage/{result_id}/review', { params: { path: { result_id: resultId } }, body })),
    onSuccess: invalidate,
  })
}

export const useAssignTicket = () => {
  const invalidate = useInvalidateTickets()
  return useMutation({
    mutationFn: ({ ticketId, assignee, by }: { ticketId: string; assignee: string; by?: string }) =>
      unwrap(api.POST('/api/tickets/{ticket_id}/assign', { params: { path: { ticket_id: ticketId } }, body: { assignee, by } })),
    onSuccess: invalidate,
  })
}

/** A specialist moving their ticket along: start, wait, resume, resolve (done). */
export const useWorkUpdate = () => {
  const invalidate = useInvalidateTickets()
  return useMutation({
    mutationFn: ({ ticketId, body }: { ticketId: string; body: WorkUpdate }) =>
      unwrap(api.POST('/api/tickets/{ticket_id}/work', { params: { path: { ticket_id: ticketId } }, body })),
    onSuccess: invalidate,
  })
}

export const useRubricPreview = () =>
  useMutation({ mutationFn: (body: RubricPreviewRequest) => unwrap(api.POST('/api/rubric/preview', { body })) })

// ------------------------------------------------------------------ people

export const useUsers = () =>
  useQuery({ queryKey: queryKeys.users, queryFn: () => unwrap(api.GET('/api/users')), staleTime: 60_000 })

export const useWorkload = (team: string | undefined) =>
  useQuery({
    queryKey: queryKeys.workload(team ?? ''),
    queryFn: () => unwrap(api.GET('/api/workload', { params: { query: { team: team! } } })),
    enabled: !!team,
  })

export const useSettings = () =>
  useQuery({ queryKey: queryKeys.settings, queryFn: () => unwrap(api.GET('/api/settings')), staleTime: Infinity })

// ------------------------------------------------------------------ knowledge base / RAG

export const useKbDocuments = (kind?: EvidenceKind) =>
  useQuery({
    queryKey: queryKeys.kbDocuments(kind),
    queryFn: () => unwrap(api.GET('/api/kb/documents', { params: { query: kind ? { kind } : {} } })),
  })

export const useKbSearch = () =>
  useMutation({ mutationFn: (body: KbSearchRequest) => unwrap(api.POST('/api/kb/search', { body })) })

export const useSyncKb = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => unwrap(api.POST('/api/kb/sync')),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['kb-documents'] }),
  })
}

export const useAskAssistant = () =>
  useMutation({ mutationFn: (body: AssistantRequest) => unwrap(api.POST('/api/assistant/ask', { body })) })

// ------------------------------------------------------------------ insights

export const useMetrics = () =>
  useQuery({ queryKey: queryKeys.metrics, queryFn: () => unwrap(api.GET('/api/metrics')) })

export const useCalibration = () =>
  useQuery({ queryKey: queryKeys.calibration, queryFn: () => unwrap(api.GET('/api/metrics/calibration')) })

export const fetchSubmission = (source: TicketSource = 'challenge') =>
  unwrap(api.GET('/api/export/submission', { params: { query: { source } } }))

// ------------------------------------------------------------------ messaging / directory / impact

export const useChannels = (asUser: string | undefined) =>
  useQuery({
    queryKey: ['channels', asUser],
    queryFn: () => unwrap(api.GET('/api/chat/channels', { params: { query: { as_user: asUser! } } })),
    enabled: !!asUser,
    refetchInterval: 5_000,
  })

export const useMessages = (channel: string | undefined) =>
  useQuery({
    queryKey: ['messages', channel],
    queryFn: () => unwrap(api.GET('/api/chat/messages', { params: { query: { channel: channel! } } })),
    enabled: !!channel,
    refetchInterval: 3_000,
  })

export const useSendMessage = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: MessageCreate) => unwrap(api.POST('/api/chat/messages', { body })),
    onSuccess: (msg) => {
      qc.invalidateQueries({ queryKey: ['messages', msg.channel] })
      qc.invalidateQueries({ queryKey: ['channels'] })
      qc.invalidateQueries({ queryKey: ['directory'] })
      if (msg.ticket_id) qc.invalidateQueries({ queryKey: ['ticket'] })
    },
  })
}

export const useDraftMessage = () =>
  useMutation({ mutationFn: (body: DraftRequest) => unwrap(api.POST('/api/chat/draft', { body })) })

export const useDirectory = () =>
  useQuery({ queryKey: ['directory'], queryFn: () => unwrap(api.GET('/api/directory')), refetchInterval: 15_000 })

export const useImpact = (includeDemo: boolean) =>
  useQuery({
    queryKey: ['impact', includeDemo],
    queryFn: () => unwrap(api.GET('/api/metrics/impact', { params: { query: { include_demo: includeDemo, days: 28 } } })),
  })
