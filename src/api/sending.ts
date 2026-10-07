import { apiRequest } from './client'

export interface ApiEmailMessage {
  id: string
  lead_id: string
  contact_id: string
  outreach_draft_id: string
  sender_email: string
  sender_name: string
  recipient_email: string
  recipient_name?: string | null
  subject: string
  body: string
  provider: string
  provider_message_id?: string | null
  status: string
  test_mode: boolean
  error_code?: string | null
  error_message?: string | null
  sent_at?: string | null
  delivered_at?: string | null
  failed_at?: string | null
  created_at: string
  updated_at: string
}

export interface SendEmailResponse {
  status: string
  message_id: string
  provider_message_id?: string | null
  test_mode: boolean
  error_code?: string | null
  error_message?: string | null
}

export interface SendingStats {
  emails_sent: number
  delivered: number
  bounced: number
  failed: number
  suppressed: number
  simulated: number
  delivery_rate?: number | null
  delivery_data_available: boolean
  has_real_data: boolean
}

export function sendOutreachDraft(draftId: string) {
  return apiRequest<SendEmailResponse>(`/api/outreach/${draftId}/send`, { method: 'POST' })
}

export function listDraftMessages(draftId: string) {
  return apiRequest<ApiEmailMessage[]>(`/api/outreach/${draftId}/messages`)
}

export function listLeadMessages(leadId: string) {
  return apiRequest<ApiEmailMessage[]>(`/api/leads/${leadId}/messages`)
}

export function getSendingStats() {
  return apiRequest<SendingStats>('/api/sending/stats')
}

export function unsubscribeEmail(email: string) {
  return apiRequest<{ status: string; email: string; reason: string }>('/api/unsubscribe', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}
