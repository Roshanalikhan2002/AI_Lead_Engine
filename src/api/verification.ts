import { apiRequest } from './client'

export type VerificationStatus =
  | 'pending'
  | 'valid'
  | 'invalid'
  | 'risky'
  | 'unknown'
  | 'blocked'
  | 'error'
  | 'not_verified'

export interface ApiEmailVerification {
  id: string
  lead_contact_id: string
  status: VerificationStatus
  provider: string
  provider_summary?: string | null
  is_valid?: boolean | null
  is_risky?: boolean | null
  is_disposable?: boolean | null
  is_role_based?: boolean | null
  is_free_provider?: boolean | null
  mx_found?: boolean | null
  domain?: string | null
  verified_at?: string | null
}

export interface VerifyResponse {
  job_id?: string | null
  status: string
  verification?: ApiEmailVerification | null
}

export interface VerificationJobStatus {
  job_id: string
  status: string
  total: number
  processed: number
  valid: number
  invalid: number
  risky: number
  unknown: number
  failed: number
  progress: number
}

export function verifyContact(leadId: string, contactId: string) {
  return apiRequest<VerifyResponse>(`/api/leads/${leadId}/contacts/${contactId}/verify`, {
    method: 'POST',
  })
}

export function reverifyContact(leadId: string, contactId: string) {
  return apiRequest<VerifyResponse>(`/api/leads/${leadId}/contacts/${contactId}/reverify`, {
    method: 'POST',
  })
}

export function verifyContactsBatch(payload: {
  contact_ids?: string[]
  lead_ids?: string[]
  only_unverified?: boolean
  discovery_confidence?: 'high' | 'medium' | 'low'
  country?: string
  industry?: string
  limit?: number
}) {
  return apiRequest<VerificationJobStatus>('/api/leads/contacts/verify-batch', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getVerificationJob(jobId: string) {
  return apiRequest<VerificationJobStatus>(`/api/leads/contact-verification-jobs/${jobId}`)
}

export async function pollVerificationJob(
  jobId: string,
  opts: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<VerificationJobStatus> {
  const intervalMs = opts.intervalMs ?? 1000
  const timeoutMs = opts.timeoutMs ?? 120_000
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const status = await getVerificationJob(jobId)
    if (status.status === 'completed' || status.status === 'failed') return status
    await new Promise((r) => window.setTimeout(r, intervalMs))
  }
  throw new Error('Email verification timed out')
}
