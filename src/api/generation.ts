import { apiRequest } from './client'

export type WebsiteFilter = 'any' | 'yes' | 'no'
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface GenerationCreatePayload {
  country: string
  state?: string | null
  city: string
  industry: string
  keywords?: string | null
  min_rating?: number | null
  min_reviews?: number | null
  website_filter: WebsiteFilter
  quantity: number
}

export interface GenerationCreateResponse {
  job_id: string
  status: JobStatus
}

export interface GenerationStatusResponse {
  job_id: string
  status: JobStatus
  found: number
  processed: number
  saved: number
  duplicates_skipped: number
  target: number
  progress: number
  country: string
  state?: string | null
  city: string
  industry: string
  error_message?: string | null
  created_at: string
  completed_at?: string | null
}

export function createGeneration(payload: GenerationCreatePayload) {
  return apiRequest<GenerationCreateResponse>('/api/generation', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getGenerationStatus(jobId: string) {
  return apiRequest<GenerationStatusResponse>(`/api/generation/${jobId}`)
}
