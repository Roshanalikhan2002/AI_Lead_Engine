import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, Filter, LayoutGrid, List, ArrowUpDown, Users, ScanSearch } from 'lucide-react'
import { PageHeader } from '@/components/shared/PageHeader'
import { SearchInput } from '@/components/shared/SearchInput'
import { Pagination } from '@/components/shared/Pagination'
import { LeadCard, LeadTable } from '@/components/shared/LeadTable'
import { SkeletonTable, SkeletonLeadCard } from '@/components/shared/Skeleton'
import { EmptyState } from '@/components/shared/EmptyState'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { industries, countries } from '@/data/mock'
import { useToast } from '@/components/shared/Toast'
import { listLeads } from '@/api/leads'
import { mapApiLeadToUi } from '@/api/mappers'
import { analyzeWebsitesBatch, pollWebsiteJob } from '@/api/websites'
import { discoverContactsBatch, pollContactJob } from '@/api/contacts'
import { pollVerificationJob, verifyContactsBatch } from '@/api/verification'
import { pollQualificationJob, qualifyLeadsBatch } from '@/api/qualification'
import { generateOutreachBatch, pollOutreachJob } from '@/api/outreach'
import { ApiError } from '@/api/client'
import type { Lead } from '@/types'

const PAGE_SIZE = 10

export function LeadsPage() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [leads, setLeads] = useState<Lead[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(0)
  const [query, setQuery] = useState('')
  const [country, setCountry] = useState('all')
  const [industry, setIndustry] = useState('all')
  const [analysisStatus, setAnalysisStatus] = useState('all')
  const [opportunity, setOpportunity] = useState('all')
  const [contactStatus, setContactStatus] = useState('all')
  const [verificationStatus, setVerificationStatus] = useState('all')
  const [discoveryConfidence, setDiscoveryConfidence] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')
  const [qualificationStatus, setQualificationStatus] = useState('all')
  const [outreachStatus, setOutreachStatus] = useState('all')
  const [sendingStatus, setSendingStatus] = useState('all')
  const [sort, setSort] = useState('newest')
  const [view, setView] = useState<'table' | 'cards'>('table')
  const [selected, setSelected] = useState<string[]>([])
  const [page, setPage] = useState(1)

  const fetchLeads = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const sortMap: Record<
        string,
        | 'newest'
        | 'oldest'
        | 'rating_desc'
        | 'rating_asc'
        | 'name'
        | 'website_score_desc'
        | 'lead_score_desc'
        | 'lead_score_asc'
      > = {
        newest: 'newest',
        oldest: 'oldest',
        'score-desc': 'rating_desc',
        'score-asc': 'rating_asc',
        'website-score': 'website_score_desc',
        'lead-score-desc': 'lead_score_desc',
        'lead-score-asc': 'lead_score_asc',
        name: 'name',
      }
      const data = await listLeads({
        page,
        limit: PAGE_SIZE,
        search: query || undefined,
        country: country === 'all' ? undefined : country,
        industry: industry === 'all' ? undefined : industry,
        website_analysis_status:
          analysisStatus === 'all'
            ? undefined
            : (analysisStatus as
                | 'not_analyzed'
                | 'pending'
                | 'running'
                | 'completed'
                | 'failed'
                | 'not_available'
                | 'blocked'),
        contact_discovery_status:
          contactStatus === 'all'
            ? undefined
            : (contactStatus as
                | 'not_discovered'
                | 'pending'
                | 'running'
                | 'completed'
                | 'failed'
                | 'not_available'
                | 'no_public_email'),
        verification_status:
          verificationStatus === 'all'
            ? undefined
            : (verificationStatus as
                | 'valid'
                | 'invalid'
                | 'risky'
                | 'unknown'
                | 'not_verified'),
        discovery_confidence:
          discoveryConfidence === 'all'
            ? undefined
            : (discoveryConfidence as 'high' | 'medium' | 'low'),
        qualification_status:
          qualificationStatus === 'all'
            ? undefined
            : (qualificationStatus as
                | 'qualified'
                | 'not_qualified'
                | 'insufficient_data'
                | 'unconfigured'
                | 'not_analyzed'),
        priority: priorityFilter === 'all' ? undefined : (priorityFilter as 'hot' | 'warm' | 'cold' | 'unknown'),
        outreach_draft_status:
          outreachStatus === 'all'
            ? undefined
            : (outreachStatus as 'not_generated' | 'draft' | 'approved' | 'rejected' | 'edited'),
        sending_status:
          sendingStatus === 'all'
            ? undefined
            : (sendingStatus as
                | 'not_sent'
                | 'approved'
                | 'simulated'
                | 'sent'
                | 'delivered'
                | 'failed'
                | 'bounced'
                | 'blocked'),
        opportunity_service: opportunity === 'all' ? undefined : opportunity,
        sort: sortMap[sort] ?? 'newest',
      })
      setLeads(data.items.map(mapApiLeadToUi))
      setTotal(data.total)
      setPages(data.pages)
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Unable to load leads. Confirm the backend is running.'
      setError(message)
      setLeads([])
      setTotal(0)
      setPages(0)
    } finally {
      setLoading(false)
    }
  }, [
    page,
    query,
    country,
    industry,
    analysisStatus,
    contactStatus,
    verificationStatus,
    discoveryConfidence,
    qualificationStatus,
    priorityFilter,
    outreachStatus,
    sendingStatus,
    opportunity,
    sort,
  ])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchLeads()
    }, 250)
    return () => window.clearTimeout(timer)
  }, [fetchLeads])

  const handleAnalyzeSelected = async () => {
    if (selected.length === 0) {
      toast({ title: 'Select leads first', type: 'info' })
      return
    }
    setAnalyzing(true)
    try {
      const started = await analyzeWebsitesBatch({ lead_ids: selected, not_analyzed: false })
      await pollWebsiteJob(started.job_id)
      toast({
        title: 'Website analysis complete',
        description: `${started.lead_ids.length} lead(s) processed.`,
        type: 'success',
      })
      setSelected([])
      await fetchLeads()
    } catch (err) {
      toast({
        title: 'Batch analysis failed',
        description: err instanceof ApiError ? err.message : 'Unable to analyze websites',
        type: 'error',
      })
    } finally {
      setAnalyzing(false)
    }
  }

  const handleAnalyzeUnanalyzed = async () => {
    setAnalyzing(true)
    try {
      const started = await analyzeWebsitesBatch({
        not_analyzed: true,
        website_exists: true,
        limit: 25,
      })
      await pollWebsiteJob(started.job_id)
      toast({
        title: 'Website analysis complete',
        description: `${started.lead_ids.length} lead(s) processed.`,
        type: 'success',
      })
      await fetchLeads()
    } catch (err) {
      toast({
        title: 'Batch analysis failed',
        description: err instanceof ApiError ? err.message : 'No matching leads or analysis failed',
        type: 'error',
      })
    } finally {
      setAnalyzing(false)
    }
  }

  const handleDiscoverContacts = async () => {
    setAnalyzing(true)
    try {
      const started = await discoverContactsBatch({
        without_contacts: true,
        website_exists: true,
        limit: 25,
      })
      await pollContactJob(started.job_id)
      toast({
        title: 'Contact discovery complete',
        description: `${started.lead_ids.length} lead(s) processed.`,
        type: 'success',
      })
      await fetchLeads()
    } catch (err) {
      toast({
        title: 'Contact discovery failed',
        description: err instanceof ApiError ? err.message : 'No matching leads or discovery failed',
        type: 'error',
      })
    } finally {
      setAnalyzing(false)
    }
  }

  const handleVerifySelected = async () => {
    if (selected.length === 0) {
      toast({ title: 'Select leads first', type: 'info' })
      return
    }
    setAnalyzing(true)
    try {
      const started = await verifyContactsBatch({
        lead_ids: selected,
        only_unverified: true,
        limit: 50,
      })
      const done = await pollVerificationJob(started.job_id)
      toast({
        title: 'Verification complete',
        description: `Valid ${done.valid} · Invalid ${done.invalid} · Risky ${done.risky} · Unknown ${done.unknown}`,
        type: 'success',
      })
      setSelected([])
      await fetchLeads()
    } catch (err) {
      toast({
        title: 'Verification failed',
        description: err instanceof ApiError ? err.message : 'Unable to verify contacts',
        type: 'error',
      })
    } finally {
      setAnalyzing(false)
    }
  }

  const handleVerifyUnverified = async () => {
    setAnalyzing(true)
    try {
      const started = await verifyContactsBatch({
        only_unverified: true,
        limit: 50,
      })
      const done = await pollVerificationJob(started.job_id)
      toast({
        title: 'Verification complete',
        description: `Valid ${done.valid} · Invalid ${done.invalid} · Risky ${done.risky} · Unknown ${done.unknown}`,
        type: 'success',
      })
      await fetchLeads()
    } catch (err) {
      toast({
        title: 'Verification failed',
        description: err instanceof ApiError ? err.message : 'No unverified contacts matched',
        type: 'error',
      })
    } finally {
      setAnalyzing(false)
    }
  }

  const handleQualifySelected = async () => {
    if (selected.length === 0) {
      toast({ title: 'Select leads first', type: 'info' })
      return
    }
    setAnalyzing(true)
    try {
      const started = await qualifyLeadsBatch({
        lead_ids: selected,
        only_unqualified: false,
        limit: 50,
      })
      const done = await pollQualificationJob(started.job_id)
      toast({
        title: 'Qualification complete',
        description: `Qualified ${done.qualified} · Insufficient ${done.insufficient_data} · Failed ${done.failed}`,
        type: 'success',
      })
      setSelected([])
      await fetchLeads()
    } catch (err) {
      toast({
        title: 'Qualification failed',
        description: err instanceof ApiError ? err.message : 'Unable to qualify leads',
        type: 'error',
      })
    } finally {
      setAnalyzing(false)
    }
  }

  const handleQualifyUnqualified = async () => {
    setAnalyzing(true)
    try {
      const started = await qualifyLeadsBatch({
        only_unqualified: true,
        website_analyzed: true,
        limit: 25,
      })
      const done = await pollQualificationJob(started.job_id)
      toast({
        title: 'Qualification complete',
        description: `Qualified ${done.qualified} · Insufficient ${done.insufficient_data} · Failed ${done.failed}`,
        type: 'success',
      })
      await fetchLeads()
    } catch (err) {
      toast({
        title: 'Qualification failed',
        description: err instanceof ApiError ? err.message : 'No unmatched leads or qualification failed',
        type: 'error',
      })
    } finally {
      setAnalyzing(false)
    }
  }

  const handleGenerateOutreach = async () => {
    setAnalyzing(true)
    try {
      const started = await generateOutreachBatch({
        lead_ids: selected.length ? selected : undefined,
        only_qualified: true,
        only_verified_contacts: true,
        without_current_draft: true,
        limit: 25,
      })
      const done = await pollOutreachJob(started.job_id)
      toast({
        title: 'Outreach drafts complete',
        description: `Generated ${done.generated} · Skipped ${done.skipped} · Failed ${done.failed}`,
        type: 'success',
      })
      setSelected([])
      await fetchLeads()
    } catch (err) {
      toast({
        title: 'Outreach generation failed',
        description: err instanceof ApiError ? err.message : 'No matching leads',
        type: 'error',
      })
    } finally {
      setAnalyzing(false)
    }
  }

  if (loading && leads.length === 0) {
    return (
      <div className="min-w-0">
        <PageHeader title="All Leads" description="Loading leads from your database..." />
        <div className="mb-4 hidden md:block">
          <SkeletonTable rows={6} />
        </div>
        <div className="grid gap-3 md:hidden">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonLeadCard key={i} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="min-w-0">
      <PageHeader
        title="All Leads"
        description={`${total.toLocaleString()} leads in your database from Google Places discovery.`}
        breadcrumbs={[{ label: 'Lead Generation' }, { label: 'All Leads' }]}
        actions={
          <>
            <Button variant="outline" disabled={analyzing} onClick={() => void handleAnalyzeSelected()}>
              <ScanSearch className="h-4 w-4" />
              <span className="hidden sm:inline">{analyzing ? 'Analyzing…' : 'Analyze Selected'}</span>
            </Button>
            <Button variant="outline" disabled={analyzing} onClick={() => void handleAnalyzeUnanalyzed()}>
              <ScanSearch className="h-4 w-4" />
              <span className="hidden sm:inline">Analyze Websites</span>
            </Button>
            <Button variant="outline" disabled={analyzing} onClick={() => void handleDiscoverContacts()}>
              <ScanSearch className="h-4 w-4" />
              <span className="hidden sm:inline">Discover Contacts</span>
            </Button>
            <Button variant="outline" disabled={analyzing} onClick={() => void handleVerifySelected()}>
              <ScanSearch className="h-4 w-4" />
              <span className="hidden sm:inline">{analyzing ? 'Verifying…' : 'Verify Selected'}</span>
            </Button>
            <Button variant="outline" disabled={analyzing} onClick={() => void handleVerifyUnverified()}>
              <ScanSearch className="h-4 w-4" />
              <span className="hidden sm:inline">Verify Unverified</span>
            </Button>
            <Button variant="outline" disabled={analyzing} onClick={() => void handleQualifySelected()}>
              <ScanSearch className="h-4 w-4" />
              <span className="hidden sm:inline">Qualify Selected</span>
            </Button>
            <Button variant="outline" disabled={analyzing} onClick={() => void handleQualifyUnqualified()}>
              <ScanSearch className="h-4 w-4" />
              <span className="hidden sm:inline">Qualify Leads</span>
            </Button>
            <Button variant="outline" disabled={analyzing} onClick={() => void handleGenerateOutreach()}>
              <ScanSearch className="h-4 w-4" />
              <span className="hidden sm:inline">Generate Emails</span>
            </Button>
            <Button variant="outline" onClick={() => toast({ title: 'Export started (demo)', type: 'info' })}>
              <Download className="h-4 w-4" />
              <span className="hidden sm:inline">Export</span>
            </Button>
            <Button onClick={() => navigate('/find-leads')}>Find Leads</Button>
          </>
        }
      />

      <div className="mb-4 flex flex-col gap-3 rounded-xl border border-border bg-card p-3 sm:p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <SearchInput
            placeholder="Search companies, industries, cities..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setPage(1)
            }}
            containerClassName="min-w-0 flex-1"
            aria-label="Search leads"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant={view === 'table' ? 'secondary' : 'ghost'}
              size="icon-sm"
              className="hidden md:inline-flex"
              onClick={() => setView('table')}
              aria-label="Table view"
            >
              <List className="h-4 w-4" />
            </Button>
            <Button
              variant={view === 'cards' ? 'secondary' : 'ghost'}
              size="icon-sm"
              onClick={() => setView('cards')}
              aria-label="Card view"
            >
              <LayoutGrid className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-8">
          <Select
            value={country}
            onValueChange={(v) => {
              setCountry(v)
              setPage(1)
            }}
          >
            <SelectTrigger aria-label="Filter by country">
              <Filter className="h-4 w-4 text-muted-foreground" aria-hidden />
              <SelectValue placeholder="Country" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All countries</SelectItem>
              {countries.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={industry}
            onValueChange={(v) => {
              setIndustry(v)
              setPage(1)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Industry" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All industries</SelectItem>
              {industries.map((i) => (
                <SelectItem key={i} value={i}>
                  {i}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={analysisStatus}
            onValueChange={(v) => {
              setAnalysisStatus(v)
              setPage(1)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Website status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All analysis statuses</SelectItem>
              <SelectItem value="not_analyzed">Not Analyzed</SelectItem>
              <SelectItem value="running">Analyzing</SelectItem>
              <SelectItem value="completed">Analyzed</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
              <SelectItem value="not_available">No Website</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={contactStatus}
            onValueChange={(v) => {
              setContactStatus(v)
              setPage(1)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Contact status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All contact statuses</SelectItem>
              <SelectItem value="not_discovered">Not Discovered</SelectItem>
              <SelectItem value="completed">Discovered</SelectItem>
              <SelectItem value="no_public_email">No Public Email</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={verificationStatus}
            onValueChange={(v) => {
              setVerificationStatus(v)
              setPage(1)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Verification" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All verification</SelectItem>
              <SelectItem value="valid">Valid</SelectItem>
              <SelectItem value="invalid">Invalid</SelectItem>
              <SelectItem value="risky">Risky</SelectItem>
              <SelectItem value="unknown">Unknown</SelectItem>
              <SelectItem value="not_verified">Not verified</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={discoveryConfidence}
            onValueChange={(v) => {
              setDiscoveryConfidence(v)
              setPage(1)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Discovery confidence" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All discovery confidence</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={priorityFilter}
            onValueChange={(v) => {
              setPriorityFilter(v)
              setPage(1)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Priority" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All priorities</SelectItem>
              <SelectItem value="hot">Hot</SelectItem>
              <SelectItem value="warm">Warm</SelectItem>
              <SelectItem value="cold">Cold</SelectItem>
              <SelectItem value="unknown">Unknown</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={qualificationStatus}
            onValueChange={(v) => {
              setQualificationStatus(v)
              setPage(1)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="AI qualification" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All qualification</SelectItem>
              <SelectItem value="qualified">Qualified</SelectItem>
              <SelectItem value="not_qualified">Not Qualified</SelectItem>
              <SelectItem value="insufficient_data">Insufficient Data</SelectItem>
              <SelectItem value="not_analyzed">Not Analyzed</SelectItem>
              <SelectItem value="unconfigured">Unconfigured</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={outreachStatus}
            onValueChange={(v) => {
              setOutreachStatus(v)
              setPage(1)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Outreach" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All outreach</SelectItem>
              <SelectItem value="not_generated">Not Generated</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
              <SelectItem value="edited">Edited</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={sendingStatus}
            onValueChange={(v) => {
              setSendingStatus(v)
              setPage(1)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Sending status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All sending</SelectItem>
              <SelectItem value="not_sent">Not Sent</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="simulated">Simulated</SelectItem>
              <SelectItem value="sent">Sent</SelectItem>
              <SelectItem value="delivered">Delivered</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
              <SelectItem value="bounced">Bounced</SelectItem>
              <SelectItem value="blocked">Blocked</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={opportunity}
            onValueChange={(v) => {
              setOpportunity(v)
              setPage(1)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Opportunity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All opportunities</SelectItem>
              <SelectItem value="website_development">Website development</SelectItem>
              <SelectItem value="website_redesign">Website redesign</SelectItem>
              <SelectItem value="appointment_automation">Appointment automation</SelectItem>
              <SelectItem value="ai_chatbot">AI chatbot</SelectItem>
              <SelectItem value="lead_capture">Lead capture</SelectItem>
            </SelectContent>
          </Select>
          <Select value={sort} onValueChange={setSort}>
            <SelectTrigger>
              <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
              <SelectValue placeholder="Sort" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="newest">Newest</SelectItem>
              <SelectItem value="oldest">Oldest</SelectItem>
              <SelectItem value="lead-score-desc">Highest AI score</SelectItem>
              <SelectItem value="lead-score-asc">Lowest AI score</SelectItem>
              <SelectItem value="website-score">Website score</SelectItem>
              <SelectItem value="score-desc">Rating: High to low</SelectItem>
              <SelectItem value="score-asc">Rating: Low to high</SelectItem>
              <SelectItem value="name">Company name</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {error ? (
        <EmptyState
          icon={Users}
          title="Unable to load leads"
          description={error}
          actionLabel="Retry"
          onAction={() => void fetchLeads()}
          secondaryLabel="Find Leads"
          onSecondary={() => navigate('/find-leads')}
        />
      ) : leads.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No leads yet"
          description="Run Find Leads to discover businesses from Google Places and save them here."
          actionLabel="Find Leads"
          onAction={() => navigate('/find-leads')}
        />
      ) : (
        <>
          <div className={view === 'table' ? 'hidden md:block' : 'hidden'}>
            <LeadTable leads={leads} selected={selected} onSelect={setSelected} />
          </div>
          <div className={view === 'table' ? 'grid gap-3 md:hidden' : 'grid gap-3 sm:grid-cols-2 xl:grid-cols-3'}>
            {leads.map((lead) => (
              <LeadCard
                key={lead.id}
                lead={lead}
                selected={selected.includes(lead.id)}
                onSelect={() =>
                  setSelected((prev) =>
                    prev.includes(lead.id) ? prev.filter((id) => id !== lead.id) : [...prev, lead.id],
                  )
                }
              />
            ))}
          </div>
          <Pagination
            className="mt-4"
            page={page}
            totalPages={Math.max(pages, 1)}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  )
}
