import { apiRequest } from './client'

export type QualificationStatus =
  | 'qualified'
  | 'not_qualified'
  | 'insufficient_data'
  | 'error'
  | 'unconfigured'
  | 'not_analyzed'

export type LeadPriority = 'hot' | 'warm' | 'cold' | 'unknown'

export interface ApiAIQualification {
  id: string
  lead_id: string
  status: QualificationStatus
  lead_score?: number | null
  priority: LeadPriority
  business_fit_score?: number | null
  website_opportunity_score?: number | null
  automation_opportunity_score?: number | null
  contactability_score?: number | null
  evidence_quality_score?: number | null
  primary_service?: string | null
  primary_opportunity_confidence?: string | null
  primary_reason?: string | null
  primary_evidence?: string[] | null
  additional_opportunities?: Array<{
    service: string
    confidence: string
    reason?: string | null
    evidence: string[]
  }> | null
  recommended_action?: string | null
  personalization_insights?: string[] | null
  qualification_summary?: string | null
  provider: string
  model?: string | null
  model_version?: string | null
  prompt_version?: string | null
  error_message?: string | null
  created_at: string
  updated_at: string
}

export interface QualifyResponse {
  job_id?: string | null
  status: string
  qualification?: ApiAIQualification | null
}

export interface QualificationJobStatus {
  job_id: string
  status: string
  total: number
  processed: number
  qualified: number
  insufficient_data: number
  failed: number
  progress: number
  error_message?: string | null
}

export interface QualificationStats {
  total_qualified: number
  hot_leads: number
  warm_leads: number
  cold_leads: number
  average_score?: number | null
  top_opportunity?: string | null
  top_industry?: string | null
  has_real_data: boolean
}

export function qualifyLead(leadId: string) {
  return apiRequest<QualifyResponse>(`/api/leads/${leadId}/qualify`, { method: 'POST' })
}

export function requalifyLead(leadId: string) {
  return apiRequest<QualifyResponse>(`/api/leads/${leadId}/requalify`, { method: 'POST' })
}

export function getQualification(leadId: string) {
  return apiRequest<ApiAIQualification>(`/api/leads/${leadId}/qualification`)
}

export function qualifyLeadsBatch(payload: {
  lead_ids?: string[]
  only_unqualified?: boolean
  country?: string
  industry?: string
  website_analyzed?: boolean
  limit?: number
}) {
  return apiRequest<QualificationJobStatus>('/api/leads/qualify-batch', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getQualificationJob(jobId: string) {
  return apiRequest<QualificationJobStatus>(`/api/leads/qualification-jobs/${jobId}`)
}

export function getQualificationStats() {
  return apiRequest<QualificationStats>('/api/qualification/stats')
}

export async function pollQualificationJob(
  jobId: string,
  opts: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<QualificationJobStatus> {
  const intervalMs = opts.intervalMs ?? 1000
  const timeoutMs = opts.timeoutMs ?? 180_000
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const status = await getQualificationJob(jobId)
    if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
      return status
    }
    await new Promise((r) => window.setTimeout(r, intervalMs))
  }
  throw new Error('AI qualification timed out')
}
