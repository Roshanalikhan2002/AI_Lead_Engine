import { apiRequest } from './client'

export type WebsiteAnalysisStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'not_available'
  | 'blocked'
  | 'not_analyzed'

export interface ApiWebsiteAnalysis {
  id: string
  lead_id: string
  website_url?: string | null
  final_url?: string | null
  http_status?: number | null
  https_enabled?: boolean | null
  reachable?: boolean | null
  performance_score?: number | null
  mobile_score?: number | null
  seo_score?: number | null
  accessibility_score?: number | null
  website_score?: number | null
  has_title?: boolean | null
  has_meta_description?: boolean | null
  has_h1?: boolean | null
  has_favicon?: boolean | null
  has_canonical?: boolean | null
  has_viewport?: boolean | null
  has_contact_form?: boolean | null
  has_booking?: boolean | null
  booking_evidence?: string[] | null
  has_chatbot?: boolean | null
  chatbot_provider?: string | null
  has_live_chat?: boolean | null
  has_phone?: boolean | null
  has_email?: boolean | null
  has_address?: boolean | null
  has_clear_cta?: boolean | null
  cta_evidence?: string[] | null
  page_count?: number | null
  load_time_ms?: number | null
  technology_detected?: string[] | null
  seo_checks?: Record<string, unknown> | null
  score_reasons?: string[] | null
  mobile_ready?: boolean | null
  analysis_status: WebsiteAnalysisStatus
  error_message?: string | null
  analyzed_at?: string | null
  created_at: string
  updated_at: string
}

export interface ApiLeadOpportunity {
  id: string
  lead_id: string
  service: string
  confidence: 'high' | 'medium' | 'low'
  reason: string
  evidence?: string[] | null
  source: string
  created_at: string
}

export interface AnalyzeStartResponse {
  job_id: string
  status: string
  lead_ids: string[]
}

export interface WebsiteJobStatus {
  job_id: string
  status: string
  total: number
  processed: number
  succeeded: number
  failed: number
  progress: number
  error_message?: string | null
}

export function analyzeWebsite(leadId: string) {
  return apiRequest<AnalyzeStartResponse>(`/api/websites/analyze/${leadId}`, { method: 'POST' })
}

export function reanalyzeWebsite(leadId: string) {
  return apiRequest<AnalyzeStartResponse>(`/api/leads/${leadId}/reanalyze-website`, { method: 'POST' })
}

export function getWebsiteAnalysis(leadId: string) {
  return apiRequest<ApiWebsiteAnalysis>(`/api/websites/${leadId}`)
}

export function analyzeWebsitesBatch(payload: {
  lead_ids?: string[]
  website_exists?: boolean
  not_analyzed?: boolean
  country?: string
  industry?: string
  limit?: number
}) {
  return apiRequest<AnalyzeStartResponse>('/api/websites/analyze-batch', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getWebsiteJob(jobId: string) {
  return apiRequest<WebsiteJobStatus>(`/api/websites/jobs/${jobId}`)
}

export async function pollWebsiteJob(
  jobId: string,
  opts: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<WebsiteJobStatus> {
  const intervalMs = opts.intervalMs ?? 1000
  const timeoutMs = opts.timeoutMs ?? 120_000
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const status = await getWebsiteJob(jobId)
    if (status.status === 'completed' || status.status === 'failed') return status
    await new Promise((r) => window.setTimeout(r, intervalMs))
  }
  throw new Error('Website analysis timed out')
}
