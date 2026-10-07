import { apiRequest } from '@/api/client'

export type ConversationStatus =
  | 'open'
  | 'interested'
  | 'meeting_requested'
  | 'not_interested'
  | 'unsubscribe'
  | 'closed'
  | 'needs_human'

export interface ApiConversation {
  id: string
  lead_id: string | null
  contact_id: string | null
  campaign_id: string | null
  status: ConversationStatus
  provider_thread_id: string | null
  last_intent: string | null
  last_message_at: string | null
  created_at: string
  updated_at: string
  business_name: string | null
  contact_email: string | null
  preview: string | null
}

export interface ApiConversationMessage {
  id: string
  conversation_id: string
  direction: 'inbound' | 'outbound'
  message_type: string
  sender_email: string | null
  recipient_email: string | null
  subject: string | null
  body: string
  sent_at: string | null
  received_at: string | null
  created_at: string
}

export interface ApiReplyClassification {
  id: string
  inbound_email_id: string
  conversation_id: string | null
  intent: string
  intent_confidence: number | null
  sentiment: string
  sentiment_confidence: number | null
  urgency: string
  requires_human: boolean
  reason: string | null
  evidence: string[] | null
  model: string | null
  provider: string
  created_at: string
}

export interface ApiReplySuggestion {
  id: string
  conversation_id: string
  inbound_email_id: string | null
  subject: string | null
  body: string
  status: string
  model: string | null
  provider: string
  created_at: string
  updated_at: string
}

export interface ReplyStats {
  total_replies: number
  conversations: number
  interested: number
  meeting_requests: number
  questions: number
  not_interested: number
  unsubscribes: number
  unknown: number
  reply_rate: number | null
  interest_rate: number | null
  meeting_request_rate: number | null
  unsubscribe_rate: number | null
  has_real_data: boolean
  reply_tracking_live: boolean
  note: string | null
}

export function listConversations(params?: { status?: string; intent?: string; sort?: string }) {
  const sp = new URLSearchParams()
  if (params?.status && params.status !== 'all') sp.set('status', params.status)
  if (params?.intent) sp.set('intent', params.intent)
  if (params?.sort) sp.set('sort', params.sort)
  const qs = sp.toString()
  return apiRequest<ApiConversation[]>(`/api/conversations${qs ? `?${qs}` : ''}`)
}

export function getConversation(id: string) {
  return apiRequest<ApiConversation>(`/api/conversations/${id}`)
}

export function listConversationMessages(id: string) {
  return apiRequest<ApiConversationMessage[]>(`/api/conversations/${id}/messages`)
}

export function getConversationClassification(id: string) {
  return apiRequest<ApiReplyClassification | null>(`/api/conversations/${id}/classification`)
}

export function listConversationSuggestions(id: string) {
  return apiRequest<ApiReplySuggestion[]>(`/api/conversations/${id}/suggestions`)
}

export function classifyConversation(id: string) {
  return apiRequest<ApiReplyClassification>(`/api/conversations/${id}/classify`, { method: 'POST' })
}

export function generateSuggestion(id: string) {
  return apiRequest<ApiReplySuggestion>(`/api/conversations/${id}/suggestions/generate`, {
    method: 'POST',
  })
}

export function regenerateSuggestion(id: string) {
  return apiRequest<ApiReplySuggestion>(`/api/conversations/${id}/suggestions/regenerate`, {
    method: 'POST',
  })
}

export function updateSuggestion(id: string, payload: { subject?: string; body?: string }) {
  return apiRequest<ApiReplySuggestion>(`/api/reply-suggestions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function approveSuggestion(id: string) {
  return apiRequest<ApiReplySuggestion>(`/api/reply-suggestions/${id}/approve`, { method: 'POST' })
}

export function rejectSuggestion(id: string) {
  return apiRequest<ApiReplySuggestion>(`/api/reply-suggestions/${id}/reject`, { method: 'POST' })
}

export function sendSuggestion(id: string) {
  return apiRequest<{ status: string; message_id: string; test_mode: boolean }>(
    `/api/reply-suggestions/${id}/send`,
    { method: 'POST' },
  )
}

export function getReplyStats() {
  return apiRequest<ReplyStats>('/api/replies/stats')
}

export function formatPct(rate: number | null | undefined): string {
  if (rate == null) return 'No data'
  return `${(rate * 100).toFixed(1)}%`
}
