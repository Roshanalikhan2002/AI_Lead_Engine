import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Download,
  ListPlus,
  MoreHorizontal,
  Send,
  ArrowLeft,
  Building2,
  MapPin,
  Phone,
  Globe,
  Star,
  Radar,
  Users,
  ScanSearch,
} from 'lucide-react'
import { PageHeader } from '@/components/shared/PageHeader'
import { ProgressRing, LeadScore } from '@/components/shared/LeadScore'
import { WebsiteScore } from '@/components/shared/WebsiteScore'
import { SkeletonProfile } from '@/components/shared/Skeleton'
import { EmptyState } from '@/components/shared/EmptyState'
import { OutreachStatusBadge } from '@/components/shared/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useToast } from '@/components/shared/Toast'
import { softTransition } from '@/lib/motion'
import { getLead } from '@/api/leads'
import { mapApiLeadToUi } from '@/api/mappers'
import { analyzeWebsite, pollWebsiteJob } from '@/api/websites'
import { discoverContacts, pollContactJob, rediscoverContacts } from '@/api/contacts'
import { verifyContact } from '@/api/verification'
import { qualifyLead } from '@/api/qualification'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  approveOutreachDraft,
  generateOutreach,
  regenerateOutreach,
  rejectOutreachDraft,
  updateOutreachDraft,
} from '@/api/outreach'
import { sendOutreachDraft } from '@/api/sending'
import { ApiError } from '@/api/client'
import type { Lead } from '@/types'

export function LeadDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [loading, setLoading] = useState(true)
  const [lead, setLead] = useState<Lead | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [discovering, setDiscovering] = useState(false)
  const [verifyingId, setVerifyingId] = useState<string | null>(null)
  const [qualifying, setQualifying] = useState(false)
  const [outreachBusy, setOutreachBusy] = useState(false)
  const [editing, setEditing] = useState(false)
  const [preview, setPreview] = useState(false)
  const [sendConfirm, setSendConfirm] = useState(false)
  const [editSubject, setEditSubject] = useState('')
  const [editBody, setEditBody] = useState('')

  const loadLead = async (leadId: string) => {
    const data = await getLead(leadId)
    setLead(mapApiLeadToUi(data))
  }

  useEffect(() => {
    if (!id) return
    let cancelled = false
    setLoading(true)
    loadLead(id)
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Lead not found')
          setLead(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id])

  const handleAnalyze = async () => {
    if (!id) return
    setAnalyzing(true)
    try {
      const started = await analyzeWebsite(id)
      await pollWebsiteJob(started.job_id)
      await loadLead(id)
      toast({ title: 'Website analysis complete', type: 'success' })
    } catch (err) {
      toast({
        title: 'Analysis failed',
        description: err instanceof ApiError ? err.message : 'Unable to analyze website',
        type: 'error',
      })
    } finally {
      setAnalyzing(false)
    }
  }

  const handleDiscoverContacts = async (force = false) => {
    if (!id) return
    setDiscovering(true)
    try {
      const job = force ? await rediscoverContacts(id) : await discoverContacts(id)
      toast({ title: force ? 'Rediscovery started' : 'Contact discovery started', type: 'info' })
      const done = await pollContactJob(job.job_id)
      await loadLead(id)
      toast({
        title: 'Contact discovery complete',
        description: `${done.succeeded} succeeded · ${done.processed}/${done.total} processed`,
        type: 'success',
      })
    } catch (err) {
      toast({
        title: 'Contact discovery failed',
        description: err instanceof ApiError ? err.message : 'Unable to discover contacts',
        type: 'error',
      })
    } finally {
      setDiscovering(false)
    }
  }

  const handleVerifyContact = async (contactId: string) => {
    if (!id) return
    setVerifyingId(contactId)
    try {
      await verifyContact(id, contactId)
      await loadLead(id)
      toast({ title: 'Verification complete', type: 'success' })
    } catch (err) {
      toast({
        title: 'Verification failed',
        description: err instanceof ApiError ? err.message : 'Unable to verify email',
        type: 'error',
      })
    } finally {
      setVerifyingId(null)
    }
  }

  const handleQualify = async () => {
    if (!id) return
    setQualifying(true)
    try {
      const result = await qualifyLead(id)
      await loadLead(id)
      toast({
        title: 'AI qualification complete',
        description: `Status: ${result.status}${result.qualification?.lead_score != null ? ` · Score ${result.qualification.lead_score}` : ''}`,
        type: 'success',
      })
    } catch (err) {
      toast({
        title: 'Qualification failed',
        description: err instanceof ApiError ? err.message : 'Unable to qualify lead',
        type: 'error',
      })
    } finally {
      setQualifying(false)
    }
  }

  const handleGenerateOutreach = async (force = false) => {
    if (!id) return
    setOutreachBusy(true)
    try {
      const result = force ? await regenerateOutreach(id) : await generateOutreach(id)
      await loadLead(id)
      toast({
        title: force ? 'Draft regenerated' : 'Draft generated',
        description: `Status: ${result.status}`,
        type: 'success',
      })
      setEditing(false)
      setPreview(false)
    } catch (err) {
      toast({
        title: 'Outreach generation failed',
        description: err instanceof ApiError ? err.message : 'Unable to generate draft',
        type: 'error',
      })
    } finally {
      setOutreachBusy(false)
    }
  }

  const startEdit = () => {
    const d = lead?.outreachDraft
    setEditSubject(d?.selectedSubject ?? '')
    setEditBody(d?.body ?? '')
    setEditing(true)
    setPreview(false)
  }

  const handleSaveEdit = async () => {
    const draftId = lead?.outreachDraft?.id
    if (!draftId || !id) return
    setOutreachBusy(true)
    try {
      await updateOutreachDraft(draftId, { selected_subject: editSubject, body: editBody })
      await loadLead(id)
      setEditing(false)
      toast({ title: 'Draft updated', type: 'success' })
    } catch (err) {
      toast({
        title: 'Update failed',
        description: err instanceof ApiError ? err.message : 'Unable to save draft',
        type: 'error',
      })
    } finally {
      setOutreachBusy(false)
    }
  }

  const handleApprove = async () => {
    const draftId = lead?.outreachDraft?.id
    if (!draftId || !id) return
    setOutreachBusy(true)
    try {
      await approveOutreachDraft(draftId)
      await loadLead(id)
      toast({ title: 'Draft approved (not sent)', description: 'Sending is a later phase.', type: 'success' })
    } catch (err) {
      toast({
        title: 'Approve failed',
        description: err instanceof ApiError ? err.message : 'Unable to approve',
        type: 'error',
      })
    } finally {
      setOutreachBusy(false)
    }
  }

  const handleReject = async () => {
    const draftId = lead?.outreachDraft?.id
    if (!draftId || !id) return
    setOutreachBusy(true)
    try {
      await rejectOutreachDraft(draftId)
      await loadLead(id)
      toast({ title: 'Draft rejected', type: 'info' })
    } catch (err) {
      toast({
        title: 'Reject failed',
        description: err instanceof ApiError ? err.message : 'Unable to reject',
        type: 'error',
      })
    } finally {
      setOutreachBusy(false)
    }
  }

  const handleSend = async () => {
    const draftId = lead?.outreachDraft?.id
    if (!draftId || !id) return
    setOutreachBusy(true)
    try {
      const result = await sendOutreachDraft(draftId)
      await loadLead(id)
      setSendConfirm(false)
      const awaiting =
        result.status === 'sent'
          ? 'Sent — awaiting delivery confirmation'
          : result.status === 'simulated'
            ? 'Simulated (test mode) — no real email delivered'
            : `Status: ${result.status}`
      toast({
        title: result.test_mode ? 'Test-mode send complete' : 'Email accepted by provider',
        description: `${awaiting}. Message ID: ${result.message_id}`,
        type: result.status === 'failed' || result.status === 'blocked' ? 'error' : 'success',
      })
    } catch (err) {
      toast({
        title: 'Send failed',
        description: err instanceof ApiError ? err.message : 'Unable to send email',
        type: 'error',
      })
    } finally {
      setOutreachBusy(false)
    }
  }

  if (loading) {
    return (
      <div>
        <PageHeader title="Lead details" description="Loading profile..." />
        <SkeletonProfile />
      </div>
    )
  }

  if (!lead || error) {
    return (
      <EmptyState
        icon={Users}
        title="Lead not found"
        description={error || 'This lead may have been removed or the link is invalid.'}
        actionLabel="Back to All Leads"
        onAction={() => navigate('/leads')}
      />
    )
  }

  const websiteScore = lead.websiteAnalysis.websiteScore
  const aiScore = lead.leadScore
  const displayScore = aiScore ?? websiteScore ?? 0
  const q = lead.qualification

  return (
    <div className="min-w-0 pb-20 sm:pb-0">
      <Link
        to="/leads"
        className="mb-3 inline-flex h-8 items-center gap-2 rounded-md px-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Back to leads
      </Link>

      <PageHeader
        title={lead.company}
        description={`${lead.industry} · ${lead.city}, ${lead.state}, ${lead.country}`}
        breadcrumbs={[{ label: 'Lead Generation' }, { label: 'All Leads' }, { label: lead.company }]}
        actions={
          <>
            <Button variant="outline" className="hidden sm:inline-flex" onClick={() => void handleAnalyze()} disabled={analyzing}>
              <ScanSearch className="h-4 w-4" />
              {analyzing ? 'Analyzing…' : 'Analyze Website'}
            </Button>
            <Button
              variant="outline"
              className="hidden sm:inline-flex"
              onClick={() => void handleQualify()}
              disabled={qualifying}
            >
              <Radar className="h-4 w-4" />
              {qualifying ? 'Qualifying…' : 'Qualify with AI'}
            </Button>
            <Button
              variant="outline"
              className="hidden sm:inline-flex"
              onClick={() => toast({ title: 'Add to list coming in a later phase', type: 'info' })}
            >
              <ListPlus className="h-4 w-4" />
              Add to List
            </Button>
            <Button
              className="hidden sm:inline-flex"
              onClick={() => void handleGenerateOutreach(false)}
              disabled={outreachBusy}
            >
              <Send className="h-4 w-4" />
              {outreachBusy ? 'Working…' : 'Generate Email'}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon" aria-label="More actions">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => void handleAnalyze()} disabled={analyzing}>
                  <ScanSearch className="h-4 w-4" /> Analyze Website
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => void handleQualify()} disabled={qualifying}>
                  <Radar className="h-4 w-4" /> Qualify with AI
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => toast({ title: 'Exported (demo)', type: 'info' })}>
                  <Download className="h-4 w-4" /> Export
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        }
      />

      <div className="mb-6 grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={softTransition}>
          <Card className="overflow-hidden">
            <div className="gradient-mesh border-b border-border p-6 text-center">
              <ProgressRing value={displayScore} size={128} strokeWidth={10} />
              <p className="mt-3 text-sm font-medium text-muted-foreground">
                {aiScore != null ? 'AI Lead Score' : 'Website Score'}
              </p>
              <p className="text-lg font-semibold">
                {aiScore != null
                  ? `${aiScore}/100`
                  : websiteScore != null
                    ? `${websiteScore}/100`
                    : 'Not scored yet'}
              </p>
              <div className="mt-3 flex justify-center">
                <LeadScore score={displayScore} />
              </div>
              {lead.priority ? (
                <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Priority: {lead.priority}
                </p>
              ) : null}
            </div>
            <CardContent className="space-y-2 p-5">
              <p className="text-sm font-medium">Qualification status</p>
              <div className="rounded-lg bg-muted/50 px-3 py-2 text-sm leading-relaxed capitalize">
                {(lead.qualificationStatus ?? 'not_analyzed').replaceAll('_', ' ')}
              </div>
              <Button className="mt-2 w-full" variant="outline" onClick={() => void handleQualify()} disabled={qualifying}>
                {qualifying ? 'Qualifying…' : 'Qualify with AI'}
              </Button>
            </CardContent>
          </Card>
        </motion.div>

        <div className="grid gap-3 sm:grid-cols-2 sm:gap-4">
          <InfoCard icon={Building2} label="Industry" value={lead.industry} delay={0.05} />
          <InfoCard icon={MapPin} label="Location" value={`${lead.city}, ${lead.country}`} delay={0.08} />
          <InfoCard icon={Phone} label="Phone" value={lead.phone ?? '—'} delay={0.11} />
          <InfoCard icon={Globe} label="Website" value={lead.website ?? 'No website'} delay={0.14} />
          <InfoCard
            icon={Star}
            label="Google rating"
            value={lead.rating ? `${lead.rating.toFixed(1)} · ${lead.reviews} reviews` : '—'}
            delay={0.17}
          />
          <InfoCard icon={Radar} label="Source" value={lead.source} delay={0.2} />
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-2 xl:gap-6">
        <Card className="h-full xl:col-span-2">
          <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
            <div>
              <CardTitle>AI Qualification</CardTitle>
              <CardDescription>
                Evidence-based scoring from structured Places, website, contact, and verification data
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" disabled={qualifying} onClick={() => void handleQualify()}>
              {qualifying ? 'Qualifying…' : q ? 'Re-run' : 'Qualify'}
            </Button>
          </CardHeader>
          <CardContent>
            {qualifying ? (
              <div className="space-y-3">
                <div className="h-20 shimmer rounded-xl bg-muted/40" />
                <div className="h-16 shimmer rounded-xl bg-muted/40" />
              </div>
            ) : !q || lead.qualificationStatus === 'not_analyzed' ? (
              <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
                <p className="font-medium">Not qualified yet</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Run Qualify with AI after website analysis and contact discovery for best results.
                </p>
              </div>
            ) : q.status === 'unconfigured' ? (
              <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
                <p className="font-medium">AI provider not configured</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Set AI_PROVIDER and AI_API_KEY on the backend. No fake qualification was generated.
                </p>
              </div>
            ) : q.status === 'error' ? (
              <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
                <p className="font-medium">Qualification error</p>
                <p className="mt-1 text-sm text-muted-foreground">{q.errorMessage || 'Provider returned an error.'}</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-2xl font-semibold tabular-nums">
                    {q.leadScore != null ? `${q.leadScore} / 100` : '—'}
                  </p>
                  <Badge className="uppercase">{q.priority}</Badge>
                  <Badge variant="secondary" className="capitalize">
                    {(q.primaryService ?? 'unknown').replaceAll('_', ' ')}
                  </Badge>
                  {q.primaryOpportunityConfidence ? (
                    <Badge variant="outline" className="capitalize">
                      {q.primaryOpportunityConfidence} confidence
                    </Badge>
                  ) : null}
                </div>
                {q.primaryReason ? <p className="text-sm text-muted-foreground">{q.primaryReason}</p> : null}
                {q.primaryEvidence && q.primaryEvidence.length > 0 ? (
                  <div>
                    <p className="mb-1 text-sm font-medium">Evidence</p>
                    <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                      {q.primaryEvidence.map((e) => (
                        <li key={e}>{e}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {q.recommendedAction ? (
                  <div>
                    <p className="mb-1 text-sm font-medium">Recommended action</p>
                    <p className="text-sm text-muted-foreground">{q.recommendedAction}</p>
                  </div>
                ) : null}
                {q.additionalOpportunities && q.additionalOpportunities.length > 0 ? (
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Additional opportunities</p>
                    {q.additionalOpportunities.map((op) => (
                      <div key={`${op.service}-${op.confidence}`} className="rounded-xl border border-border p-3">
                        <p className="font-medium capitalize">{op.service.replaceAll('_', ' ')}</p>
                        <p className="text-xs capitalize text-muted-foreground">{op.confidence} confidence</p>
                        {op.reason ? <p className="mt-1 text-sm text-muted-foreground">{op.reason}</p> : null}
                      </div>
                    ))}
                  </div>
                ) : null}
                {q.personalizationInsights && q.personalizationInsights.length > 0 ? (
                  <div>
                    <p className="mb-1 text-sm font-medium">Personalization insights</p>
                    <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                      {q.personalizationInsights.map((insight) => (
                        <li key={insight}>{insight}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {(q.businessFitScore != null || q.websiteOpportunityScore != null) && (
                  <div className="grid gap-2 sm:grid-cols-5 text-xs text-muted-foreground">
                    <span>Business fit: {q.businessFitScore ?? '—'}</span>
                    <span>Website: {q.websiteOpportunityScore ?? '—'}</span>
                    <span>Automation: {q.automationOpportunityScore ?? '—'}</span>
                    <span>Contact: {q.contactabilityScore ?? '—'}</span>
                    <span>Evidence: {q.evidenceQualityScore ?? '—'}</span>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <WebsiteScore analysis={lead.websiteAnalysis} analyzing={analyzing} />

        <Card className="h-full">
          <CardHeader>
            <CardTitle>Potential Opportunities</CardTitle>
            <CardDescription>Evidence-based service suggestions (not AI-generated)</CardDescription>
          </CardHeader>
          <CardContent>
            {lead.opportunities.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
                <p className="font-medium">No opportunities yet</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Run website analysis to detect potential service opportunities from measurable signals.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {lead.opportunities.map((op) => (
                  <div key={op.id} className="rounded-xl border border-border p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium capitalize">{op.name}</p>
                      <Badge variant="secondary">{op.confidence}% confidence signal</Badge>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">{op.reason}</p>
                    {op.evidence ? (
                      <p className="mt-2 text-xs text-muted-foreground">Evidence: {op.evidence}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
            <div>
              <CardTitle>Contact Discovery</CardTitle>
              <CardDescription>
                Public emails found on the business website. Discovery confidence is separate from deliverability.
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" disabled={discovering} onClick={() => void handleDiscoverContacts()}>
              {discovering ? 'Discovering…' : 'Discover Contacts'}
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {discovering ? (
              <div className="space-y-3">
                <div className="h-16 shimmer rounded-xl bg-muted/40" />
                <div className="h-16 shimmer rounded-xl bg-muted/40" />
              </div>
            ) : lead.contactDiscoveryStatus === 'no_public_email' ||
              (lead.contactDiscoveryStatus === 'completed' && !(lead.discoveredContacts?.length)) ? (
              <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
                <p className="font-medium">No public business email found</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Discovery does not invent addresses. Try again after the website changes, or use another source later.
                </p>
              </div>
            ) : lead.contactDiscoveryStatus === 'not_discovered' || !lead.discoveredContacts?.length ? (
              <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
                <p className="font-medium">Contacts not discovered yet</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Run Discover Contacts to extract publicly listed emails from the website.
                </p>
              </div>
            ) : lead.contactDiscoveryStatus === 'failed' ? (
              <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
                <p className="font-medium">Contact discovery failed</p>
                <p className="mt-1 text-sm text-muted-foreground">The website could not be reached for email discovery.</p>
              </div>
            ) : (
              lead.discoveredContacts?.map((c) => {
                const vStatus = c.verificationStatus ?? c.verification?.status ?? 'not_verified'
                const verifying = verifyingId === c.id
                return (
                  <div key={c.id} className="rounded-xl border border-border p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-medium break-all">{c.email}</p>
                          {c.isPrimary ? <Badge>Primary</Badge> : null}
                          <Badge variant="secondary" className="capitalize">
                            {c.contactType}
                          </Badge>
                        </div>
                        <div className="mt-3 grid gap-1 text-sm">
                          <p>
                            <span className="text-muted-foreground">Discovery: </span>
                            <span className="capitalize font-medium">{c.confidence}</span>
                            <span className="text-muted-foreground"> · {sourceLabel(c.source)}</span>
                          </p>
                          <p>
                            <span className="text-muted-foreground">Verification: </span>
                            <span className="font-medium">{verificationLabel(vStatus)}</span>
                          </p>
                        </div>
                        {c.sourceUrl ? (
                          <p className="mt-1 truncate text-xs text-muted-foreground" title={c.sourceUrl}>
                            {c.sourceUrl}
                          </p>
                        ) : null}
                        {c.contactName ? <p className="mt-1 text-sm">Name signal: {c.contactName}</p> : null}
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={verifying || verifyingId !== null}
                        onClick={() => void handleVerifyContact(c.id)}
                      >
                        {verifying ? 'Verifying…' : 'Verify Email'}
                      </Button>
                    </div>
                  </div>
                )
              })
            )}
            <div className="border-t border-border pt-3 text-xs text-muted-foreground">
              Discovery confidence and verification status are separate. Verification never invents deliverability.
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
            <div>
              <CardTitle>Outreach</CardTitle>
              <CardDescription>
                Personalized draft only — emails are never sent in this phase
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={outreachBusy}
                onClick={() => void handleGenerateOutreach(Boolean(lead.outreachDraft))}
              >
                {outreachBusy ? 'Working…' : lead.outreachDraft ? 'Regenerate' : 'Generate Email'}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted-foreground">Status</span>
              <OutreachStatusBadge status={lead.outreachStatus} />
              {lead.outreachReady ? <Badge variant="secondary">Email Ready</Badge> : null}
            </div>
            <div className="grid gap-2 text-sm sm:grid-cols-2">
              <Row label="Lead score" value={lead.leadScore != null ? String(lead.leadScore) : '—'} />
              <Row
                label="Service"
                value={
                  (lead.outreachDraft?.service || lead.primaryService || 'unknown').replaceAll('_', ' ')
                }
              />
              <Row label="Contact" value={lead.outreachDraft?.contactEmail || lead.contact.email || '—'} />
              <Row
                label="Verification"
                value={verificationLabel(lead.outreachDraft?.contactVerificationStatus || 'not_verified')}
              />
            </div>

            {outreachBusy ? (
              <div className="space-y-3">
                <div className="h-10 shimmer rounded-xl bg-muted/40" />
                <div className="h-28 shimmer rounded-xl bg-muted/40" />
              </div>
            ) : !lead.outreachDraft || lead.outreachDraftStatus === 'not_generated' ? (
              <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
                <p className="font-medium">No outreach draft yet</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Requires a qualified lead with a valid verified contact and known primary service.
                </p>
              </div>
            ) : lead.outreachDraft.generationStatus === 'unconfigured' ? (
              <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
                <p className="font-medium">AI provider not configured</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Set AI_PROVIDER and AI_API_KEY on the backend. No fake draft was generated.
                </p>
              </div>
            ) : lead.outreachDraft.generationStatus === 'insufficient_data' ? (
              <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
                <p className="font-medium">Insufficient data</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {lead.outreachDraft.errorMessage || 'Primary service unknown or qualification missing.'}
                </p>
              </div>
            ) : lead.outreachDraft.generationStatus === 'error' ? (
              <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
                <p className="font-medium">Generation error</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {lead.outreachDraft.errorMessage || 'Provider returned an error.'}
                </p>
              </div>
            ) : editing ? (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="outreach-subject">Subject</Label>
                  <Input
                    id="outreach-subject"
                    value={editSubject}
                    onChange={(e) => setEditSubject(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="outreach-body">Body</Label>
                  <Textarea
                    id="outreach-body"
                    rows={10}
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    {editBody.length} characters · {editBody.trim() ? editBody.trim().split(/\s+/).length : 0}{' '}
                    words
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" disabled={outreachBusy} onClick={() => void handleSaveEdit()}>
                    Save
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : preview ? (
              <div className="space-y-3 rounded-xl border border-border bg-muted/20 p-4 text-sm">
                <Row label="From" value="LeadFlow AI" />
                <Row label="To" value={lead.outreachDraft.contactEmail || '—'} />
                <Row label="Subject" value={lead.outreachDraft.selectedSubject || '—'} />
                <div className="whitespace-pre-wrap border-t border-border pt-3 leading-relaxed">
                  {lead.outreachDraft.body}
                </div>
                <Button size="sm" variant="outline" onClick={() => setPreview(false)}>
                  Close preview
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-muted-foreground">Subject</p>
                  <p className="font-medium">{lead.outreachDraft.selectedSubject || '—'}</p>
                  {lead.outreachDraft.alternativeSubjects?.length ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Alternatives: {lead.outreachDraft.alternativeSubjects.join(' · ')}
                    </p>
                  ) : null}
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Body</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">{lead.outreachDraft.body}</p>
                </div>
                {lead.outreachDraft.personalizationPoints?.length ? (
                  <div>
                    <p className="mb-1 text-sm font-medium">Personalization evidence</p>
                    <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                      {lead.outreachDraft.personalizationPoints.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={startEdit}>
                    Edit
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setPreview(true)}>
                    Preview
                  </Button>
                  <Button size="sm" disabled={outreachBusy} onClick={() => void handleApprove()}>
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={outreachBusy}
                    onClick={() => void handleReject()}
                  >
                    Reject
                  </Button>
                  {lead.outreachDraft.status === 'approved' ? (
                    <Button size="sm" disabled={outreachBusy} onClick={() => setSendConfirm(true)}>
                      Send Email
                    </Button>
                  ) : null}
                </div>
                {lead.latestEmailMessage ? (
                  <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
                    <p className="font-medium">Sending status: {lead.latestEmailMessage.status}</p>
                    <p className="mt-1 text-muted-foreground">
                      {lead.latestEmailMessage.testMode
                        ? 'Test mode — not a real delivery.'
                        : lead.latestEmailMessage.status === 'delivered'
                          ? 'Provider confirmed delivery.'
                          : lead.latestEmailMessage.status === 'sent'
                            ? 'Sent — awaiting delivery confirmation.'
                            : lead.latestEmailMessage.errorMessage || 'See message log for details.'}
                    </p>
                    {lead.latestEmailMessage.providerMessageId ? (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Provider ID: {lead.latestEmailMessage.providerMessageId}
                      </p>
                    ) : null}
                  </div>
                ) : null}
                {sendConfirm ? (
                  <div className="space-y-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4">
                    <p className="text-sm font-medium">This will send a real email (unless test mode is enabled).</p>
                    <p className="text-xs text-muted-foreground">
                      From configured sender · To {lead.outreachDraft.contactEmail} · Approved subject/body + unsubscribe
                      footer
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" disabled={outreachBusy} onClick={() => void handleSend()}>
                        {outreachBusy ? 'Sending…' : 'Confirm Send'}
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setSendConfirm(false)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Approve then Send Email. Sending is never automatic. Delivery is only shown after provider confirmation.
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function sourceLabel(source: string): string {
  if (source.includes('contact')) return 'Found on website contact page'
  if (source.includes('about')) return 'Found on about page'
  if (source.includes('team')) return 'Found on team page'
  if (source.includes('homepage')) return 'Found on homepage'
  if (source.includes('booking')) return 'Found on booking page'
  return 'Found on website'
}

function verificationLabel(status: string): string {
  switch (status) {
    case 'valid':
      return 'Valid'
    case 'invalid':
      return 'Invalid'
    case 'risky':
      return 'Risky'
    case 'unknown':
      return 'Unknown'
    case 'pending':
      return 'Pending'
    case 'blocked':
      return 'Blocked'
    case 'error':
      return 'Error'
    case 'not_verified':
    default:
      return 'Not verified'
  }
}

function InfoCard({
  icon: Icon,
  label,
  value,
  delay = 0,
}: {
  icon: typeof Building2
  label: string
  value: string
  delay?: number
}) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ ...softTransition, delay }}>
      <Card className="h-full">
        <CardContent className="flex items-start gap-3 p-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon className="h-4 w-4" aria-hidden />
          </div>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="truncate font-medium" title={value}>
              {value}
            </p>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 text-sm">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="min-w-0 break-all text-right font-medium">{value}</span>
    </div>
  )
}
