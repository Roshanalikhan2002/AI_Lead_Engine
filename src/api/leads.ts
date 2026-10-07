import { apiRequest } from './client'
import type { ApiLeadContact, ContactDiscoveryStatus } from './contacts'
import type { ApiLeadOpportunity, ApiWebsiteAnalysis, WebsiteAnalysisStatus } from './websites'
import type { VerificationStatus } from './verification'
import type { ApiAIQualification, QualificationStatus, LeadPriority } from './qualification'

export interface ApiLead {
  id: string
  external_id?: string | null
  company_name: string
  industry?: string | null
  country?: string | null
  state?: string | null
  city?: string | null
  address?: string | null
  phone?: string | null
  website?: string | null
  google_place_id?: string | null
  google_maps_url?: string | null
  rating?: number | null
  review_count?: number | null
  business_status?: string | null
  latitude?: number | null
  longitude?: number | null
  source: string
  normalized_phone?: string | null
  normalized_domain?: string | null
  generation_job_id?: string | null
  created_at: string
  updated_at: string
  website_analysis_status?: WebsiteAnalysisStatus | null
  website_score?: number | null
  website_analysis?: ApiWebsiteAnalysis | null
  opportunities?: ApiLeadOpportunity[]
  contact_discovery_status?: ContactDiscoveryStatus | null
  contact_email_count?: number
  contacts_verified_count?: number
  contacts_invalid_count?: number
  contacts_risky_count?: number
  contacts_unknown_count?: number
  contacts_unverified_count?: number
  contacts?: ApiLeadContact[]
  qualification_status?: QualificationStatus | null
  lead_score?: number | null
  priority?: LeadPriority | null
  primary_service?: string | null
  qualification?: ApiAIQualification | null
  outreach_draft_status?: string | null
  outreach_ready?: boolean
  outreach_draft?: import('./outreach').ApiOutreachDraft | null
  sending_status?: string | null
  latest_email_message?: import('./sending').ApiEmailMessage | null
}

export interface LeadListResponse {
  items: ApiLead[]
  total: number
  page: number
  limit: number
  pages: number
}

export interface LeadListParams {
  page?: number
  limit?: number
  search?: string
  country?: string
  state?: string
  city?: string
  industry?: string
  website_filter?: 'any' | 'yes' | 'no'
  website_analysis_status?: WebsiteAnalysisStatus | 'all'
  contact_discovery_status?: ContactDiscoveryStatus | 'all'
  verification_status?: VerificationStatus | 'all'
  discovery_confidence?: 'high' | 'medium' | 'low' | 'all'
  qualification_status?: QualificationStatus | 'all'
  priority?: LeadPriority | 'all'
  outreach_draft_status?: 'not_generated' | 'draft' | 'approved' | 'rejected' | 'edited' | 'all'
  sending_status?:
    | 'not_sent'
    | 'approved'
    | 'simulated'
    | 'sent'
    | 'delivered'
    | 'failed'
    | 'bounced'
    | 'blocked'
    | 'all'
  min_lead_score?: number
  min_website_score?: number
  opportunity_service?: string
  source?: string
  sort?:
    | 'newest'
    | 'oldest'
    | 'rating_desc'
    | 'rating_asc'
    | 'name'
    | 'website_score_desc'
    | 'lead_score_desc'
    | 'lead_score_asc'
}

export function listLeads(params: LeadListParams = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '' || value === 'all' || value === 'any') return
    query.set(key, String(value))
  })
  const qs = query.toString()
  return apiRequest<LeadListResponse>(`/api/leads${qs ? `?${qs}` : ''}`)
}

export function getLead(leadId: string) {
  return apiRequest<ApiLead>(`/api/leads/${leadId}`)
}
