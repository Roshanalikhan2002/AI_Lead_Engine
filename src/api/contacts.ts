import { apiRequest } from './client'
import type { ApiEmailVerification, VerificationStatus } from './verification'

export type ContactConfidence = 'high' | 'medium' | 'low'
export type ContactDiscoveryStatus =
  | 'not_discovered'
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'not_available'
  | 'no_public_email'

export interface ApiLeadContact {
  id: string
  lead_id: string
  email: string
  normalized_email: string
  contact_name?: string | null
  role?: string | null
  contact_type: string
  source: string
  source_url?: string | null
  confidence: ContactConfidence
  domain_match: boolean
  is_primary: boolean
  created_at: string
  updated_at: string
  verification?: ApiEmailVerification | null
  verification_status?: VerificationStatus | null
}

export interface DiscoverContactsResponse {
  job_id: string
  status: string
  lead_ids: string[]
}

export interface ContactJobStatus {
  job_id: string
  status: string
  total: number
  processed: number
  succeeded: number
  failed: number
  progress: number
  error_message?: string | null
}

export function discoverContacts(leadId: string) {
  return apiRequest<DiscoverContactsResponse>(`/api/leads/${leadId}/discover-contacts`, {
    method: 'POST',
  })
}

export function rediscoverContacts(leadId: string) {
  return apiRequest<DiscoverContactsResponse>(`/api/leads/${leadId}/contacts/rediscover`, {
    method: 'POST',
  })
}

export function listContacts(leadId: string) {
  return apiRequest<ApiLeadContact[]>(`/api/leads/${leadId}/contacts`)
}

export function discoverContactsBatch(payload: {
  lead_ids?: string[]
  website_exists?: boolean
  without_contacts?: boolean
  country?: string
  industry?: string
  limit?: number
}) {
  return apiRequest<DiscoverContactsResponse>('/api/leads/contacts/discover-batch', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getContactJob(jobId: string) {
  return apiRequest<ContactJobStatus>(`/api/leads/contact-jobs/${jobId}`)
}

export async function pollContactJob(
  jobId: string,
  opts: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<ContactJobStatus> {
  const intervalMs = opts.intervalMs ?? 1000
  const timeoutMs = opts.timeoutMs ?? 120_000
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const status = await getContactJob(jobId)
    if (status.status === 'completed' || status.status === 'failed') return status
    await new Promise((r) => window.setTimeout(r, intervalMs))
  }
  throw new Error('Contact discovery timed out')
}
