import type { DiscoveredContact, Lead, Opportunity, WebsiteAnalysis, WebsiteStatus } from '@/types'
import type { ApiLead } from '@/api/leads'
import type { ApiLeadContact } from '@/api/contacts'
import type { ApiLeadOpportunity, ApiWebsiteAnalysis } from '@/api/websites'

const CONFIDENCE_NUM = { high: 90, medium: 65, low: 40 } as const

/** Map Phase-1/2/3 API lead into existing UI Lead shape. */
export function mapApiLeadToUi(lead: ApiLead): Lead {
  const hasWebsite = Boolean(lead.website)
  const analysis = lead.website_analysis
  const status = lead.website_analysis_status ?? (analysis?.analysis_status || 'not_analyzed')
  const contacts = (lead.contacts ?? []).map(mapDiscoveredContact)
  const primary = contacts.find((c) => c.isPrimary) ?? contacts[0]
  const ai = lead.qualification
  const aiScore = lead.lead_score ?? ai?.lead_score ?? null

  const draft = lead.outreach_draft
  const draftStatus = lead.outreach_draft_status ?? 'not_generated'
  const mappedOutreach =
    draftStatus === 'approved'
      ? 'approved'
      : draftStatus === 'rejected'
        ? 'rejected'
        : draftStatus === 'edited'
          ? 'edited'
          : draftStatus === 'draft'
            ? 'draft'
            : 'not_started'

  return {
    id: lead.id,
    company: lead.company_name,
    industry: lead.industry ?? '—',
    country: lead.country ?? '—',
    state: lead.state ?? '—',
    city: lead.city ?? '—',
    website: lead.website ?? undefined,
    phone: lead.phone ?? undefined,
    rating: lead.rating ?? 0,
    reviews: lead.review_count ?? 0,
    opportunity: mapPrimaryOpportunity(lead.opportunities) !== 'Pending analysis'
      ? mapPrimaryOpportunity(lead.opportunities)
      : lead.primary_service
        ? lead.primary_service.replaceAll('_', ' ')
        : 'Pending analysis',
    score: aiScore ?? lead.website_score ?? 0,
    emailStatus:
      primary?.verificationStatus === 'valid'
        ? 'verified'
        : primary?.verificationStatus === 'invalid'
          ? 'invalid'
          : primary
            ? 'unverified'
            : 'pending',
    outreachStatus: mappedOutreach,
    websiteStatus: mapWebsiteStatus(status, hasWebsite, lead.website_score, analysis),
    websiteAnalysisStatus: status,
    contactDiscoveryStatus: lead.contact_discovery_status ?? 'not_discovered',
    contactEmailCount: lead.contact_email_count ?? contacts.length,
    contactsVerifiedCount: lead.contacts_verified_count ?? 0,
    contactsInvalidCount: lead.contacts_invalid_count ?? 0,
    contactsRiskyCount: lead.contacts_risky_count ?? 0,
    contactsUnknownCount: lead.contacts_unknown_count ?? 0,
    contactsUnverifiedCount: lead.contacts_unverified_count ?? 0,
    discoveredContacts: contacts,
    qualificationStatus: lead.qualification_status ?? 'not_analyzed',
    leadScore: aiScore,
    priority: lead.priority ?? ai?.priority ?? null,
    primaryService: lead.primary_service ?? ai?.primary_service ?? null,
    qualification: ai
      ? {
          status: ai.status,
          leadScore: ai.lead_score,
          priority: ai.priority,
          businessFitScore: ai.business_fit_score,
          websiteOpportunityScore: ai.website_opportunity_score,
          automationOpportunityScore: ai.automation_opportunity_score,
          contactabilityScore: ai.contactability_score,
          evidenceQualityScore: ai.evidence_quality_score,
          primaryService: ai.primary_service,
          primaryOpportunityConfidence: ai.primary_opportunity_confidence,
          primaryReason: ai.primary_reason,
          primaryEvidence: ai.primary_evidence ?? [],
          additionalOpportunities: (ai.additional_opportunities ?? []).map((o) => ({
            service: o.service,
            confidence: o.confidence,
            reason: o.reason,
            evidence: o.evidence ?? [],
          })),
          recommendedAction: ai.recommended_action,
          personalizationInsights: ai.personalization_insights ?? [],
          qualificationSummary: ai.qualification_summary,
          provider: ai.provider,
          errorMessage: ai.error_message,
        }
      : undefined,
    outreachDraftStatus: draftStatus,
    outreachReady: Boolean(lead.outreach_ready),
    outreachDraft: draft
      ? {
          id: draft.id,
          contactId: draft.contact_id,
          status: draft.status,
          selectedSubject: draft.selected_subject ?? undefined,
          alternativeSubjects: draft.alternative_subjects ?? undefined,
          body: draft.body ?? undefined,
          service: draft.service ?? undefined,
          personalizationPoints: draft.personalization_points ?? undefined,
          generationStatus: draft.generation_status ?? undefined,
          contactEmail: draft.contact_email ?? undefined,
          contactVerificationStatus: draft.contact_verification_status ?? undefined,
          provider: draft.provider,
          errorMessage: draft.error_message ?? undefined,
        }
      : undefined,
    sendingStatus: lead.sending_status ?? 'not_sent',
    latestEmailMessage: lead.latest_email_message
      ? {
          id: lead.latest_email_message.id,
          status: lead.latest_email_message.status,
          testMode: lead.latest_email_message.test_mode,
          providerMessageId: lead.latest_email_message.provider_message_id ?? undefined,
          sentAt: lead.latest_email_message.sent_at ?? undefined,
          deliveredAt: lead.latest_email_message.delivered_at ?? undefined,
          errorMessage: lead.latest_email_message.error_message ?? undefined,
        }
      : undefined,
    source:
      lead.source === 'google_places_mock'
        ? 'google_places_mock (offline QA)'
        : lead.source || 'google_places',
    createdAt: lead.created_at,
    contact: {
      name: primary?.contactName || (primary ? '—' : 'Not enriched yet'),
      title: primary ? primary.contactType : '—',
      email: primary?.email || '—',
      emailStatus: primary ? 'unverified' : 'pending',
      phone: lead.phone ?? undefined,
    },
    websiteAnalysis: mapWebsiteAnalysis(hasWebsite, status, analysis),
    opportunities: (lead.opportunities ?? []).map(mapOpportunity),
    scoreReasons: ai?.qualification_summary
      ? [ai.qualification_summary]
      : analysis?.score_reasons?.map(String) ?? [
          status === 'not_analyzed'
            ? 'Website not analyzed yet'
            : 'AI qualification not run yet',
        ],
    outreach: {
      status: mappedOutreach,
    },
  }
}

function mapDiscoveredContact(c: ApiLeadContact): DiscoveredContact {
  return {
    id: c.id,
    email: c.email,
    contactName: c.contact_name ?? undefined,
    contactType: c.contact_type,
    confidence: c.confidence,
    source: c.source,
    sourceUrl: c.source_url ?? undefined,
    domainMatch: c.domain_match,
    isPrimary: c.is_primary,
    verificationStatus: c.verification_status ?? c.verification?.status ?? 'not_verified',
    verification: c.verification
      ? {
          status: c.verification.status,
          isRoleBased: c.verification.is_role_based ?? undefined,
          isFreeProvider: c.verification.is_free_provider ?? undefined,
          isDisposable: c.verification.is_disposable ?? undefined,
          mxFound: c.verification.mx_found,
          provider: c.verification.provider,
        }
      : undefined,
  }
}

function mapPrimaryOpportunity(ops?: ApiLeadOpportunity[]): string {
  if (!ops?.length) return 'Pending analysis'
  return ops[0].service.replaceAll('_', ' ')
}

function mapWebsiteStatus(
  status: string,
  hasWebsite: boolean,
  score: number | null | undefined,
  analysis?: ApiWebsiteAnalysis | null,
): WebsiteStatus {
  if (!hasWebsite || status === 'not_available') return 'none'
  if (status === 'failed' || status === 'blocked') return 'poor'
  if (status === 'pending' || status === 'running' || status === 'not_analyzed') return 'average'
  const value = score ?? analysis?.website_score
  if (value == null) return 'average'
  if (value >= 80) return 'excellent'
  if (value >= 65) return 'good'
  if (value >= 45) return 'average'
  return 'poor'
}

function mapWebsiteAnalysis(
  hasWebsite: boolean,
  status: string,
  analysis?: ApiWebsiteAnalysis | null,
): WebsiteAnalysis {
  if (!hasWebsite || status === 'not_available') {
    return {
      exists: false,
      performance: 0,
      mobile: 0,
      seo: 0,
      accessibility: 0,
      ctaQuality: 0,
      hasBooking: false,
      hasContactForm: false,
      hasChatbot: false,
      issues: [{ label: 'No website detected', severity: 'high' }],
      analysisStatus: 'not_available',
      scoreReasons: ['No website on lead record'],
    }
  }

  if (!analysis || status === 'not_analyzed' || status === 'pending' || status === 'running') {
    return {
      exists: true,
      performance: 0,
      mobile: 0,
      seo: 0,
      accessibility: 0,
      ctaQuality: 0,
      hasBooking: false,
      hasContactForm: false,
      hasChatbot: false,
      issues: [],
      analysisStatus: (status as WebsiteAnalysis['analysisStatus']) || 'not_analyzed',
      scoreReasons: [],
    }
  }

  if (status === 'failed' || status === 'blocked') {
    return {
      exists: true,
      performance: 0,
      mobile: 0,
      seo: 0,
      accessibility: 0,
      ctaQuality: 0,
      hasBooking: false,
      hasContactForm: false,
      hasChatbot: false,
      issues: [{ label: analysis.error_message || 'Website could not be analyzed', severity: 'high' }],
      analysisStatus: status as WebsiteAnalysis['analysisStatus'],
      httpsEnabled: analysis.https_enabled ?? undefined,
      reachable: analysis.reachable ?? undefined,
      loadTimeMs: analysis.load_time_ms ?? undefined,
      technology: analysis.technology_detected?.map(String),
      scoreReasons: analysis.score_reasons?.map(String),
      errorMessage: analysis.error_message ?? undefined,
    }
  }

  const issues: WebsiteAnalysis['issues'] = []
  if (analysis.has_meta_description === false) {
    issues.push({ label: 'Missing meta description', severity: 'medium' })
  }
  if (analysis.has_viewport === false) {
    issues.push({ label: 'Missing mobile viewport', severity: 'high' })
  }
  if (analysis.has_clear_cta === false) {
    issues.push({ label: 'Weak or missing clear CTA', severity: 'medium' })
  }
  if (analysis.has_booking === false) {
    issues.push({ label: 'No online booking detected', severity: 'low' })
  }
  if (analysis.https_enabled === false) {
    issues.push({ label: 'HTTPS not detected', severity: 'high' })
  }

  return {
    exists: true,
    performance: analysis.performance_score ?? 0,
    mobile: analysis.mobile_score ?? 0,
    seo: analysis.seo_score ?? 0,
    accessibility: analysis.accessibility_score ?? 0,
    ctaQuality: analysis.has_clear_cta ? 80 : 25,
    hasBooking: Boolean(analysis.has_booking),
    hasContactForm: Boolean(analysis.has_contact_form),
    hasChatbot: Boolean(analysis.has_chatbot),
    issues,
    analysisStatus: 'completed',
    httpsEnabled: analysis.https_enabled ?? undefined,
    reachable: analysis.reachable ?? undefined,
    loadTimeMs: analysis.load_time_ms ?? undefined,
    technology: analysis.technology_detected?.map(String),
    scoreReasons: analysis.score_reasons?.map(String),
    websiteScore: analysis.website_score ?? undefined,
    performanceMeasured: analysis.performance_score != null,
    mobileMeasured: analysis.mobile_score != null,
    seoMeasured: analysis.seo_score != null,
    accessibilityMeasured: analysis.accessibility_score != null,
    finalUrl: analysis.final_url ?? undefined,
    chatbotProvider: analysis.chatbot_provider ?? undefined,
  }
}

function mapOpportunity(op: ApiLeadOpportunity): Opportunity {
  return {
    id: op.id,
    name: op.service.replaceAll('_', ' '),
    confidence: CONFIDENCE_NUM[op.confidence],
    reason: op.reason,
    evidence: (op.evidence ?? []).join('; '),
    recommendedService: op.service,
  }
}
