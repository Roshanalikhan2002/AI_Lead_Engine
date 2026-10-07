import { apiRequest } from './client'

export type OutreachDraftStatus = 'draft' | 'approved' | 'rejected' | 'edited' | 'cancelled'

export interface ApiOutreachDraft {
  id: string
  lead_id: string
  contact_id: string
  status: OutreachDraftStatus | string
  selected_subject?: string | null
  alternative_subjects?: string[] | null
  body?: string | null
  service?: string | null
  personalization_points?: string[] | null
  provider: string
  model?: string | null
  model_version?: string | null
  prompt_version?: string | null
  error_message?: string | null
  generation_status?: string | null
  contact_email?: string | null
  contact_verification_status?: string | null
  created_at: string
  updated_at: string
}

export interface OutreachGenerateResponse {
  job_id?: string | null
  status: string
  draft?: ApiOutreachDraft | null
}

export interface OutreachJobStatus {
  job_id: string
  status: string
  total: number
  processed: number
  generated: number
  skipped: number
  failed: number
  progress: number
}

export function generateOutreach(leadId: string, contactId?: string) {
  return apiRequest<OutreachGenerateResponse>(`/api/leads/${leadId}/outreach/generate`, {
    method: 'POST',
    body: JSON.stringify(contactId ? { contact_id: contactId } : {}),
  })
}

export function regenerateOutreach(leadId: string, contactId?: string) {
  return apiRequest<OutreachGenerateResponse>(`/api/leads/${leadId}/outreach/regenerate`, {
    method: 'POST',
    body: JSON.stringify(contactId ? { contact_id: contactId } : {}),
  })
}

export function listLeadOutreach(leadId: string) {
  return apiRequest<ApiOutreachDraft[]>(`/api/leads/${leadId}/outreach`)
}

export function getOutreachDraft(draftId: string) {
  return apiRequest<ApiOutreachDraft>(`/api/outreach/${draftId}`)
}

export function regenerateOutreachDraft(draftId: string) {
  return apiRequest<OutreachGenerateResponse>(`/api/outreach/${draftId}/regenerate`, {
    method: 'POST',
  })
}

export function updateOutreachDraft(draftId: string, payload: { selected_subject?: string; body?: string }) {
  return apiRequest<ApiOutreachDraft>(`/api/outreach/${draftId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function approveOutreachDraft(draftId: string) {
  return apiRequest<ApiOutreachDraft>(`/api/outreach/${draftId}/approve`, { method: 'POST' })
}

export function rejectOutreachDraft(draftId: string) {
  return apiRequest<ApiOutreachDraft>(`/api/outreach/${draftId}/reject`, { method: 'POST' })
}

export function generateOutreachBatch(payload: {
  lead_ids?: string[]
  priority?: 'hot' | 'warm' | 'cold'
  only_qualified?: boolean
  only_verified_contacts?: boolean
  without_current_draft?: boolean
  limit?: number
}) {
  return apiRequest<OutreachJobStatus>('/api/outreach/generate-batch', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getOutreachJob(jobId: string) {
  return apiRequest<OutreachJobStatus>(`/api/outreach/jobs/${jobId}`)
}

export async function pollOutreachJob(
  jobId: string,
  opts: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<OutreachJobStatus> {
  const intervalMs = opts.intervalMs ?? 1000
  const timeoutMs = opts.timeoutMs ?? 180_000
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const status = await getOutreachJob(jobId)
    if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
      return status
    }
    await new Promise((r) => window.setTimeout(r, intervalMs))
  }
  throw new Error('Outreach generation timed out')
}
