import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Inbox, RefreshCw, Sparkles } from 'lucide-react'
import { PageHeader } from '@/components/shared/PageHeader'
import { EmptyState } from '@/components/shared/EmptyState'
import { SearchInput } from '@/components/shared/SearchInput'
import { SkeletonTable } from '@/components/shared/Skeleton'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/components/shared/Toast'
import { ApiError } from '@/api/client'
import { cn } from '@/lib/utils'
import {
  approveSuggestion,
  classifyConversation,
  generateSuggestion,
  getConversationClassification,
  listConversationMessages,
  listConversationSuggestions,
  listConversations,
  regenerateSuggestion,
  rejectSuggestion,
  sendSuggestion,
  updateSuggestion,
  type ApiConversation,
  type ApiConversationMessage,
  type ApiReplyClassification,
  type ApiReplySuggestion,
} from '@/api/replies'

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'interested', label: 'Interested' },
  { value: 'meeting_requested', label: 'Meeting Requested' },
  { value: 'needs_human', label: 'Needs Human' },
  { value: 'not_interested', label: 'Not Interested' },
  { value: 'unsubscribe', label: 'Unsubscribe' },
  { value: 'open', label: 'Open' },
]

function formatWhen(value: string | null) {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function confLabel(value: number | null | undefined) {
  if (value == null) return '—'
  return `${Math.round(value * 100)}%`
}

export function RepliesPage() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [loading, setLoading] = useState(true)
  const [conversations, setConversations] = useState<ApiConversation[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ApiConversationMessage[]>([])
  const [classification, setClassification] = useState<ApiReplyClassification | null>(null)
  const [suggestion, setSuggestion] = useState<ApiReplySuggestion | null>(null)
  const [draft, setDraft] = useState('')
  const [draftSubject, setDraftSubject] = useState('')
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sort, setSort] = useState('newest')
  const [mobileShowThread, setMobileShowThread] = useState(false)
  const [busy, setBusy] = useState(false)

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await listConversations({ status: statusFilter, sort })
      setConversations(rows)
      if (!selectedId && rows[0]) setSelectedId(rows[0].id)
    } catch (err) {
      toast({
        title: 'Failed to load conversations',
        description: err instanceof ApiError ? err.message : 'Unknown error',
        type: 'error',
      })
    } finally {
      setLoading(false)
    }
  }, [selectedId, sort, statusFilter, toast])

  const loadThread = useCallback(
    async (id: string) => {
      try {
        const [msgs, cls, suggestions] = await Promise.all([
          listConversationMessages(id),
          getConversationClassification(id),
          listConversationSuggestions(id),
        ])
        setMessages(msgs)
        setClassification(cls)
        const latest = suggestions[0] ?? null
        setSuggestion(latest)
        setDraft(latest?.body ?? '')
        setDraftSubject(latest?.subject ?? '')
      } catch (err) {
        toast({
          title: 'Failed to load thread',
          description: err instanceof ApiError ? err.message : 'Unknown error',
          type: 'error',
        })
      }
    },
    [toast],
  )

  useEffect(() => {
    void loadList()
  }, [loadList])

  useEffect(() => {
    if (selectedId) void loadThread(selectedId)
  }, [selectedId, loadThread])

  const filtered = useMemo(() => {
    if (!query) return conversations
    const q = query.toLowerCase()
    return conversations.filter(
      (c) =>
        (c.business_name || '').toLowerCase().includes(q) ||
        (c.contact_email || '').toLowerCase().includes(q) ||
        (c.preview || '').toLowerCase().includes(q) ||
        (c.last_intent || '').toLowerCase().includes(q),
    )
  }, [conversations, query])

  const selected = filtered.find((c) => c.id === selectedId) ?? filtered[0]

  async function refreshSuggestion(id: string) {
    const suggestions = await listConversationSuggestions(id)
    const latest = suggestions[0] ?? null
    setSuggestion(latest)
    setDraft(latest?.body ?? '')
    setDraftSubject(latest?.subject ?? '')
  }

  if (loading && conversations.length === 0) {
    return (
      <div>
        <PageHeader title="Replies" description="Loading inbox..." />
        <SkeletonTable rows={6} />
      </div>
    )
  }

  if (!loading && conversations.length === 0) {
    return (
      <div>
        <PageHeader
          title="Replies"
          description="Reply tracking is ready. No conversations yet."
          breadcrumbs={[{ label: 'Outreach' }, { label: 'Replies' }]}
        />
        <EmptyState
          icon={Inbox}
          title="No replies yet"
          description="Inbound replies appear here after a configured provider webhook or mock intake. Reply detection is not live-tested by default."
          actionLabel="View Campaigns"
          onAction={() => navigate('/campaigns')}
        />
      </div>
    )
  }

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title="Replies"
        description="AI-classified inbox. AI never auto-sends — review and approve before sending."
        breadcrumbs={[{ label: 'Outreach' }, { label: 'Replies' }]}
        actions={
          <Button variant="outline" size="sm" onClick={() => void loadList()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        }
      />

      <div className="flex flex-wrap gap-2">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter" />
          </SelectTrigger>
          <SelectContent>
            {FILTERS.map((f) => (
              <SelectItem key={f.value} value={f.value}>
                {f.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={sort} onValueChange={setSort}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Sort" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="newest">Newest</SelectItem>
            <SelectItem value="oldest">Oldest</SelectItem>
            <SelectItem value="priority">Highest Priority</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid min-w-0 gap-4 lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)_300px]">
        <Card className={cn('overflow-hidden', mobileShowThread ? 'hidden lg:block' : 'block')}>
          <CardHeader className="border-b border-border p-3">
            <SearchInput
              placeholder="Search conversations..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search replies"
            />
          </CardHeader>
          <CardContent className="max-h-[60dvh] space-y-1 overflow-y-auto p-2 lg:max-h-[70dvh]">
            {filtered.map((thread) => (
              <button
                key={thread.id}
                type="button"
                onClick={() => {
                  setSelectedId(thread.id)
                  setMobileShowThread(true)
                }}
                className={cn(
                  'w-full rounded-lg p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  selected?.id === thread.id ? 'bg-primary/10' : 'hover:bg-muted/50',
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="truncate text-sm font-medium">{thread.business_name || 'Unmatched'}</p>
                  <Badge variant="outline" className="shrink-0 text-[10px]">
                    {thread.status}
                  </Badge>
                </div>
                <p className="truncate text-xs text-muted-foreground">{thread.contact_email || '—'}</p>
                <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{thread.preview}</p>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  {thread.last_intent || 'unclassified'} · {formatWhen(thread.last_message_at)}
                </p>
              </button>
            ))}
          </CardContent>
        </Card>

        {selected ? (
          <Card
            className={cn(
              'min-h-[480px] min-w-0 flex-col overflow-hidden lg:flex lg:min-h-[520px]',
              mobileShowThread ? 'flex' : 'hidden lg:flex',
            )}
          >
            <CardHeader className="border-b border-border">
              <div className="mb-2 lg:hidden">
                <Button variant="ghost" size="sm" className="-ml-2" onClick={() => setMobileShowThread(false)}>
                  ← Conversations
                </Button>
              </div>
              <CardTitle className="text-base leading-snug">
                {selected.business_name || 'Unmatched conversation'}
              </CardTitle>
              <CardDescription>
                {selected.contact_email || 'No contact'} · {selected.status}
                {selected.last_intent ? ` · ${selected.last_intent}` : ''}
              </CardDescription>
              {selected.status === 'meeting_requested' ? (
                <div className="mt-3">
                  <Button
                    size="sm"
                    onClick={async () => {
                      try {
                        const types = await (await import('@/api/meetings')).listMeetingTypes(true)
                        if (!types[0]) {
                          toast({
                            title: 'Create a meeting type in Settings first',
                            type: 'warning',
                          })
                          return
                        }
                        const token = await (
                          await import('@/api/meetings')
                        ).createBookingToken({
                          meeting_type_id: types[0].id,
                          lead_id: selected.lead_id || undefined,
                          contact_id: selected.contact_id || undefined,
                          conversation_id: selected.id,
                        })
                        toast({
                          title: 'Booking link ready',
                          description: token.booking_url,
                          type: 'success',
                        })
                        window.open(token.booking_url, '_blank')
                      } catch (err) {
                        toast({
                          title: 'Could not create booking link',
                          description: err instanceof ApiError ? err.message : 'Unknown error',
                          type: 'error',
                        })
                      }
                    }}
                  >
                    Schedule Meeting
                  </Button>
                </div>
              ) : null}
            </CardHeader>
            <CardContent className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
              <div className="space-y-3">
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={cn(
                      'rounded-lg border p-3 text-sm',
                      m.direction === 'inbound' ? 'bg-muted/40' : 'bg-primary/5',
                    )}
                  >
                    <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                      <span>{m.direction === 'inbound' ? m.sender_email : 'You'}</span>
                      <span>{formatWhen(m.received_at || m.sent_at || m.created_at)}</span>
                    </div>
                    {m.subject ? <p className="mb-1 font-medium">{m.subject}</p> : null}
                    <p className="whitespace-pre-wrap text-sm">{m.body}</p>
                  </div>
                ))}
              </div>

              <div className="mt-auto space-y-3 border-t pt-4">
                <p className="text-xs font-medium text-warning">
                  AI-generated response — review before sending.
                </p>
                <Textarea
                  value={draftSubject}
                  onChange={(e) => setDraftSubject(e.target.value)}
                  placeholder="Subject"
                  className="min-h-[40px]"
                />
                <Textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Suggested reply…"
                  rows={6}
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true)
                      try {
                        if (suggestion) {
                          await regenerateSuggestion(selected.id)
                        } else {
                          await generateSuggestion(selected.id)
                        }
                        await refreshSuggestion(selected.id)
                        toast({ title: 'Suggestion ready', type: 'success' })
                      } catch (err) {
                        toast({
                          title: 'Generate failed',
                          description: err instanceof ApiError ? err.message : 'Unknown error',
                          type: 'error',
                        })
                      } finally {
                        setBusy(false)
                      }
                    }}
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    {suggestion ? 'Regenerate' : 'Generate Reply'}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy || !suggestion}
                    onClick={async () => {
                      if (!suggestion) return
                      setBusy(true)
                      try {
                        await updateSuggestion(suggestion.id, { subject: draftSubject, body: draft })
                        await approveSuggestion(suggestion.id)
                        await refreshSuggestion(selected.id)
                        toast({ title: 'Approved', type: 'success' })
                      } catch (err) {
                        toast({
                          title: 'Approve failed',
                          description: err instanceof ApiError ? err.message : 'Unknown error',
                          type: 'error',
                        })
                      } finally {
                        setBusy(false)
                      }
                    }}
                  >
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy || !suggestion}
                    onClick={async () => {
                      if (!suggestion) return
                      setBusy(true)
                      try {
                        await rejectSuggestion(suggestion.id)
                        await refreshSuggestion(selected.id)
                        toast({ title: 'Rejected', type: 'info' })
                      } catch (err) {
                        toast({
                          title: 'Reject failed',
                          description: err instanceof ApiError ? err.message : 'Unknown error',
                          type: 'error',
                        })
                      } finally {
                        setBusy(false)
                      }
                    }}
                  >
                    Reject
                  </Button>
                  <Button
                    size="sm"
                    disabled={busy || suggestion?.status !== 'approved'}
                    onClick={async () => {
                      if (!suggestion || suggestion.status !== 'approved') return
                      setBusy(true)
                      try {
                        const result = await sendSuggestion(suggestion.id)
                        toast({
                          title: result.test_mode ? 'Simulated send' : 'Sent',
                          description: `Status: ${result.status}`,
                          type: 'success',
                        })
                        await loadThread(selected.id)
                      } catch (err) {
                        toast({
                          title: 'Send failed',
                          description: err instanceof ApiError ? err.message : 'Unknown error',
                          type: 'error',
                        })
                      } finally {
                        setBusy(false)
                      }
                    }}
                  >
                    Send
                  </Button>
                </div>
                {suggestion ? (
                  <p className="text-xs text-muted-foreground">
                    Suggestion status: {suggestion.status} · provider: {suggestion.provider}
                  </p>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ) : null}

        <Card className="hidden xl:block">
          <CardHeader>
            <CardTitle className="text-base">AI classification</CardTitle>
            <CardDescription>Evidence from the inbound email only.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {classification ? (
              <>
                <div>
                  <p className="text-muted-foreground">Intent</p>
                  <p className="font-medium capitalize">{classification.intent.replaceAll('_', ' ')}</p>
                  <p className="text-xs text-muted-foreground">
                    Confidence: {confLabel(classification.intent_confidence)}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Sentiment</p>
                  <p className="font-medium capitalize">{classification.sentiment}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Urgency</p>
                  <p className="font-medium capitalize">{classification.urgency}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Status</p>
                  <p className="font-medium capitalize">{selected?.status.replaceAll('_', ' ')}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Reason</p>
                  <p>{classification.reason || '—'}</p>
                </div>
                {classification.evidence && classification.evidence.length > 0 ? (
                  <div>
                    <p className="text-muted-foreground">Evidence</p>
                    <ul className="list-disc pl-4">
                      {classification.evidence.map((e) => (
                        <li key={e}>{e}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy || !selected}
                  onClick={async () => {
                    if (!selected) return
                    setBusy(true)
                    try {
                      const row = await classifyConversation(selected.id)
                      setClassification(row)
                      await loadList()
                    } catch (err) {
                      toast({
                        title: 'Classify failed',
                        description: err instanceof ApiError ? err.message : 'Unknown error',
                        type: 'error',
                      })
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  Re-classify
                </Button>
              </>
            ) : (
              <p className="text-muted-foreground">No classification yet.</p>
            )}
            <p className="text-xs text-muted-foreground">
              Reply detection provider not live-tested. Mock classifications are labeled provider=mock.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
