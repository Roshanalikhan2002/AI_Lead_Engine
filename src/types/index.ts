export type LeadScoreTier = 'hot' | 'warm' | 'potential' | 'low'

export type EmailStatus = 'verified' | 'unverified' | 'invalid' | 'pending'
export type OutreachStatus =
  | 'not_started'
  | 'draft'
  | 'approved'
  | 'rejected'
  | 'edited'
  | 'queued'
  | 'sent'
  | 'replied'
  | 'meeting'
  | 'bounced'
export type WebsiteStatus = 'none' | 'poor' | 'average' | 'good' | 'excellent'
export type CampaignStatus = 'draft' | 'running' | 'paused' | 'completed'
export type MeetingStatus = 'scheduled' | 'completed' | 'cancelled' | 'no_show'
export type ReplyIntent = 'interested' | 'need_pricing' | 'not_interested' | 'maybe_later' | 'meeting_request'

export interface WebsiteAnalysis {
  exists: boolean
  performance: number
  mobile: number
  seo: number
  accessibility: number
  ctaQuality: number
  hasBooking: boolean
  hasContactForm: boolean
  hasChatbot: boolean
  issues: Array<{ label: string; severity: 'high' | 'medium' | 'low' }>
  analysisStatus?:
    | 'pending'
    | 'running'
    | 'completed'
    | 'failed'
    | 'not_available'
    | 'blocked'
    | 'not_analyzed'
  httpsEnabled?: boolean
  reachable?: boolean
  loadTimeMs?: number
  technology?: string[]
  scoreReasons?: string[]
  websiteScore?: number
  performanceMeasured?: boolean
  mobileMeasured?: boolean
  seoMeasured?: boolean
  accessibilityMeasured?: boolean
  finalUrl?: string
  chatbotProvider?: string
  errorMessage?: string
}

export interface Opportunity {
  id: string
  name: string
  confidence: number
  reason: string
  evidence: string
  recommendedService: string
}

export interface Contact {
  name: string
  title: string
  email: string
  emailStatus: EmailStatus
  phone?: string
}

export interface DiscoveredContact {
  id: string
  email: string
  contactName?: string
  contactType: string
  confidence: 'high' | 'medium' | 'low'
  source: string
  sourceUrl?: string
  domainMatch: boolean
  isPrimary: boolean
  verificationStatus?: string
  verification?: {
    status: string
    isRoleBased?: boolean
    isFreeProvider?: boolean
    isDisposable?: boolean
    mxFound?: boolean | null
    provider?: string
  }
}

export interface Lead {
  id: string
  company: string
  industry: string
  country: string
  state: string
  city: string
  website?: string
  phone?: string
  rating: number
  reviews: number
  opportunity: string
  score: number
  emailStatus: EmailStatus
  outreachStatus: OutreachStatus
  websiteStatus: WebsiteStatus
  websiteAnalysisStatus?: string
  contactDiscoveryStatus?: string
  contactEmailCount?: number
  contactsVerifiedCount?: number
  contactsInvalidCount?: number
  contactsRiskyCount?: number
  contactsUnknownCount?: number
  contactsUnverifiedCount?: number
  discoveredContacts?: DiscoveredContact[]
  qualificationStatus?: string
  leadScore?: number | null
  priority?: string | null
  primaryService?: string | null
  qualification?: {
    status: string
    leadScore?: number | null
    priority: string
    businessFitScore?: number | null
    websiteOpportunityScore?: number | null
    automationOpportunityScore?: number | null
    contactabilityScore?: number | null
    evidenceQualityScore?: number | null
    primaryService?: string | null
    primaryOpportunityConfidence?: string | null
    primaryReason?: string | null
    primaryEvidence?: string[]
    additionalOpportunities?: Array<{
      service: string
      confidence: string
      reason?: string | null
      evidence: string[]
    }>
    recommendedAction?: string | null
    personalizationInsights?: string[]
    qualificationSummary?: string | null
    provider?: string
    errorMessage?: string | null
  }
  outreachDraftStatus?: string
  outreachReady?: boolean
  outreachDraft?: {
    id: string
    contactId: string
    status: string
    selectedSubject?: string
    alternativeSubjects?: string[]
    body?: string
    service?: string
    personalizationPoints?: string[]
    generationStatus?: string
    contactEmail?: string
    contactVerificationStatus?: string
    provider?: string
    errorMessage?: string
  }
  sendingStatus?: string
  latestEmailMessage?: {
    id: string
    status: string
    testMode: boolean
    providerMessageId?: string
    sentAt?: string
    deliveredAt?: string
    errorMessage?: string
  }
  source: string
  createdAt: string
  contact: Contact
  websiteAnalysis: WebsiteAnalysis
  opportunities: Opportunity[]
  scoreReasons: string[]
  outreach?: {
    status: OutreachStatus
    lastEmail?: string
    nextFollowUp?: string
    replyStatus?: string
  }
}

export interface Campaign {
  id: string
  name: string
  audience: string
  leads: number
  sent: number
  replies: number
  meetings: number
  status: CampaignStatus
  template: string
  sender: string
  createdAt: string
  sequence: Array<{ type: 'email' | 'wait'; label: string; delayDays?: number }>
}

export interface EmailTemplate {
  id: string
  name: string
  subject: string
  body: string
  updatedAt: string
}

export interface ReplyThread {
  id: string
  leadId: string
  company: string
  contactName: string
  subject: string
  preview: string
  intent: ReplyIntent
  confidence: number
  unread: boolean
  updatedAt: string
  messages: Array<{
    id: string
    from: 'user' | 'lead'
    body: string
    at: string
  }>
  suggestedReply: string
}

export interface Meeting {
  id: string
  company: string
  contact: string
  date: string
  time: string
  type: string
  status: MeetingStatus
  notes?: string
}

export interface LeadList {
  id: string
  name: string
  count: number
  createdAt: string
  updatedAt: string
  description?: string
}

export interface LeadSource {
  id: string
  name: string
  leads: number
  quality: number
  status: 'active' | 'paused'
}

export function scoreTier(score: number): LeadScoreTier {
  if (score >= 90) return 'hot'
  if (score >= 70) return 'warm'
  if (score >= 50) return 'potential'
  return 'low'
}

export function scoreLabel(score: number): string {
  const tier = scoreTier(score)
  return { hot: 'Hot', warm: 'Warm', potential: 'Potential', low: 'Low' }[tier]
}
