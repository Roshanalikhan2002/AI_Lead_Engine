import { apiRequest } from '@/api/client'

export type CampaignStatus = 'draft' | 'active' | 'paused' | 'completed' | 'cancelled'

export interface ApiCampaign {
  id: string
  name: string
  description: string | null
  status: CampaignStatus
  timezone: string
  daily_send_limit: number
  hourly_send_limit: number
  send_start_hour: number
  send_end_hour: number
  send_on_weekends: boolean
  start_at: string | null
  end_at: string | null
  created_at: string
  updated_at: string
  recipients_count?: number | null
  active_count?: number | null
  replied_count?: number | null
  sent_count?: number | null
  delivered_count?: number | null
  bounced_count?: number | null
  completed_count?: number | null
}

export interface ApiCampaignStep {
  id: string
  campaign_id: string
  step_number: number
  type: string
  delay_minutes: number
  outreach_draft_id: string | null
  created_at: string
  updated_at: string
}

export interface ApiCampaignRecipient {
  id: string
  campaign_id: string
  lead_id: string
  contact_id: string
  outreach_draft_id: string
  status: string
  current_step: number
  next_action_at: string | null
  enrolled_at: string
  completed_at: string | null
  last_sent_at: string | null
  last_error: string | null
  business_name: string | null
  email: string | null
}

export interface CampaignAnalytics {
  campaign_id: string
  status: string
  recipients: number
  active: number
  completed: number
  sent: number
  delivered: number
  bounced: number
  replied: number
  unsubscribed: number
  failed: number
  delivery_rate: number | null
  reply_rate: number | null
  bounce_rate: number | null
  unsubscribe_rate: number | null
  reply_detection_configured: boolean
  reply_detection_note: string
  has_send_data: boolean
  status_breakdown: Record<string, number>
}

export interface CampaignStepInput {
  step_number: number
  type?: string
  delay_minutes: number
  outreach_draft_id?: string | null
}

export interface CreateCampaignInput {
  name: string
  description?: string | null
  timezone?: string
  daily_send_limit?: number
  hourly_send_limit?: number
  send_start_hour?: number
  send_end_hour?: number
  send_on_weekends?: boolean
  steps?: CampaignStepInput[]
}

export function listCampaigns() {
  return apiRequest<ApiCampaign[]>('/api/campaigns')
}

export function getCampaign(id: string) {
  return apiRequest<ApiCampaign>(`/api/campaigns/${id}`)
}

export function createCampaign(payload: CreateCampaignInput) {
  return apiRequest<ApiCampaign>('/api/campaigns', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateCampaign(id: string, payload: Partial<CreateCampaignInput>) {
  return apiRequest<ApiCampaign>(`/api/campaigns/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function activateCampaign(id: string) {
  return apiRequest<ApiCampaign>(`/api/campaigns/${id}/activate`, { method: 'POST' })
}

export function pauseCampaign(id: string) {
  return apiRequest<ApiCampaign>(`/api/campaigns/${id}/pause`, { method: 'POST' })
}

export function resumeCampaign(id: string) {
  return apiRequest<ApiCampaign>(`/api/campaigns/${id}/resume`, { method: 'POST' })
}

export function cancelCampaign(id: string) {
  return apiRequest<ApiCampaign>(`/api/campaigns/${id}/cancel`, { method: 'POST' })
}

export function enrollBatch(
  id: string,
  payload: {
    lead_ids?: string[]
    min_score?: number
    priority?: string
    primary_service?: string
  },
) {
  return apiRequest<{
    enrolled: Array<{ lead_id: string; contact_id: string; recipient_id: string }>
    skipped: Array<{ lead_id: string; reason: string }>
    enrolled_count: number
    skipped_count: number
  }>(`/api/campaigns/${id}/enroll-batch`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listCampaignRecipients(id: string) {
  return apiRequest<ApiCampaignRecipient[]>(`/api/campaigns/${id}/recipients`)
}

export function listCampaignSteps(id: string) {
  return apiRequest<ApiCampaignStep[]>(`/api/campaigns/${id}/steps`)
}

export function getCampaignAnalytics(id: string) {
  return apiRequest<CampaignAnalytics>(`/api/campaigns/${id}/analytics`)
}

export function processDueCampaigns(limit = 25) {
  return apiRequest<{ processed: number; results: unknown[] }>(
    `/api/campaigns/process-due?limit=${limit}`,
    { method: 'POST' },
  )
}

export function formatRate(rate: number | null | undefined): string {
  if (rate == null) return 'No data'
  return `${(rate * 100).toFixed(1)}%`
}
