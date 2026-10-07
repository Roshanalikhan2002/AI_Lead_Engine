import { apiRequest } from '@/api/client'

export interface MeetingType {
  id: string
  name: string
  description: string | null
  duration_minutes: number
  buffer_before_minutes: number
  buffer_after_minutes: number
  active: boolean
}

export interface AvailabilityRule {
  id: string
  day_of_week: number
  start_time: string
  end_time: string
  timezone: string
  active: boolean
}

export interface TimeSlot {
  start_at: string
  end_at: string
  timezone: string
}

export interface ApiMeeting {
  id: string
  lead_id: string | null
  contact_id: string | null
  conversation_id: string | null
  meeting_type_id: string
  status: string
  title: string
  description: string | null
  start_at: string
  end_at: string
  timezone: string
  meeting_url: string | null
  external_event_id: string | null
  external_provider: string | null
  prospect_name: string | null
  prospect_email: string | null
  outcome: string | null
  business_name: string | null
  meeting_type_name: string | null
  calendar_live: boolean
}

export interface BookingPublic {
  token: string
  meeting_type: MeetingType
  timezone: string
  business_name: string | null
  expires_at: string
  calendar_live: boolean
}

export interface PipelineBoard {
  stages: string[]
  columns: Record<string, Array<{
    id: string
    company_name: string
    pipeline_stage: string
    lead_score: number | null
    priority: string | null
    updated_at: string | null
  }>>
  calendar_live: boolean
}

export interface PipelineStats {
  total_leads: number
  by_stage: Record<string, number>
  qualification_rate: number | null
  reply_rate: number | null
  meeting_request_rate: number | null
  booking_rate: number | null
  meeting_completion_rate: number | null
  win_rate: number | null
  has_real_data: boolean
  calendar_live: boolean
  revenue: null
  note: string | null
  meeting_requested: number
  meeting_scheduled: number
  meeting_completed: number
  won: number
  lost: number
  replies: number
}

export function listMeetingTypes(activeOnly = false) {
  return apiRequest<MeetingType[]>(`/api/meeting-types${activeOnly ? '?active_only=true' : ''}`)
}

export function createMeetingType(payload: Partial<MeetingType> & { name: string }) {
  return apiRequest<MeetingType>('/api/meeting-types', { method: 'POST', body: JSON.stringify(payload) })
}

export function listAvailability() {
  return apiRequest<AvailabilityRule[]>('/api/availability')
}

export function createAvailability(payload: {
  day_of_week: number
  start_time: string
  end_time: string
  timezone?: string
}) {
  return apiRequest<AvailabilityRule>('/api/availability', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteAvailability(id: string) {
  return apiRequest<void>(`/api/availability/${id}`, { method: 'DELETE' })
}

export function listMeetingSlots(params: {
  meeting_type_id: string
  start_date?: string
  end_date?: string
  timezone?: string
}) {
  const sp = new URLSearchParams({ meeting_type_id: params.meeting_type_id })
  if (params.start_date) sp.set('start_date', params.start_date)
  if (params.end_date) sp.set('end_date', params.end_date)
  if (params.timezone) sp.set('timezone', params.timezone)
  return apiRequest<TimeSlot[]>(`/api/meeting-slots?${sp}`)
}

export function listMeetings(status?: string) {
  const qs = status ? `?status=${encodeURIComponent(status)}` : ''
  return apiRequest<ApiMeeting[]>(`/api/meetings${qs}`)
}

export function cancelMeeting(id: string) {
  return apiRequest<ApiMeeting>(`/api/meetings/${id}/cancel`, { method: 'POST' })
}

export function completeMeeting(id: string, outcome?: string) {
  return apiRequest<ApiMeeting>(`/api/meetings/${id}/complete`, {
    method: 'POST',
    body: JSON.stringify({ outcome: outcome || 'unknown' }),
  })
}

export function noShowMeeting(id: string) {
  return apiRequest<ApiMeeting>(`/api/meetings/${id}/no-show`, { method: 'POST' })
}

export function rescheduleMeeting(id: string, start_at: string, timezone?: string) {
  return apiRequest<ApiMeeting>(`/api/meetings/${id}/reschedule`, {
    method: 'POST',
    body: JSON.stringify({ start_at, timezone }),
  })
}

export function bookMeeting(payload: Record<string, unknown>) {
  return apiRequest<ApiMeeting>('/api/meetings/book', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function createBookingToken(payload: {
  meeting_type_id: string
  lead_id?: string
  contact_id?: string
  conversation_id?: string
}) {
  return apiRequest<{ token: string; booking_url: string; expires_at: string; calendar_live: boolean }>(
    '/api/booking-tokens',
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function getPublicBooking(token: string) {
  return apiRequest<BookingPublic>(`/api/bookings/${token}`)
}

export function getCalendarStatus() {
  return apiRequest<{ provider: string; configured: boolean; calendar_live: boolean; note: string }>(
    '/api/calendar/status',
  )
}

export function getPipelineBoard() {
  return apiRequest<PipelineBoard>('/api/pipeline')
}

export function getPipelineStats() {
  return apiRequest<PipelineStats>('/api/pipeline/stats')
}

export function updateLeadPipeline(leadId: string, stage: string, reason?: string) {
  return apiRequest<{ lead_id: string; pipeline_stage: string }>(`/api/leads/${leadId}/pipeline`, {
    method: 'PATCH',
    body: JSON.stringify({ stage, reason }),
  })
}

export function getLeadMeetings(leadId: string) {
  return apiRequest<ApiMeeting[]>(`/api/leads/${leadId}/meetings`)
}

export function formatPct(rate: number | null | undefined) {
  if (rate == null) return 'No data'
  return `${(rate * 100).toFixed(1)}%`
}
