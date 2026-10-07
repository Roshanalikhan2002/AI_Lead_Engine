import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Pause, Play, RefreshCw, XCircle } from 'lucide-react'
import { PageHeader } from '@/components/shared/PageHeader'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/shared/Toast'
import { ApiError } from '@/api/client'
import {
  activateCampaign,
  cancelCampaign,
  formatRate,
  getCampaign,
  getCampaignAnalytics,
  listCampaignRecipients,
  listCampaignSteps,
  pauseCampaign,
  processDueCampaigns,
  resumeCampaign,
  type ApiCampaign,
  type ApiCampaignRecipient,
  type ApiCampaignStep,
  type CampaignAnalytics,
} from '@/api/campaigns'

function statusVariant(
  status: string,
): 'default' | 'secondary' | 'success' | 'warning' | 'destructive' | 'outline' {
  switch (status) {
    case 'active':
      return 'success'
    case 'paused':
      return 'warning'
    case 'cancelled':
    case 'failed':
    case 'bounced':
      return 'destructive'
    case 'completed':
    case 'replied':
      return 'secondary'
    default:
      return 'outline'
  }
}

function formatWhen(value: string | null) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

export function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [campaign, setCampaign] = useState<ApiCampaign | null>(null)
  const [steps, setSteps] = useState<ApiCampaignStep[]>([])
  const [recipients, setRecipients] = useState<ApiCampaignRecipient[]>([])
  const [analytics, setAnalytics] = useState<CampaignAnalytics | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!id) return
    setLoading(true)
    try {
      const [c, s, r, a] = await Promise.all([
        getCampaign(id),
        listCampaignSteps(id),
        listCampaignRecipients(id),
        getCampaignAnalytics(id),
      ])
      setCampaign(c)
      setSteps(s)
      setRecipients(r)
      setAnalytics(a)
    } catch (err) {
      toast({
        title: 'Failed to load campaign',
        description: err instanceof ApiError ? err.message : 'Unknown error',
        type: 'error',
      })
    } finally {
      setLoading(false)
    }
  }, [id, toast])

  useEffect(() => {
    void load()
  }, [load])

  async function runAction(action: 'activate' | 'pause' | 'resume' | 'cancel') {
    if (!id) return
    setBusy(true)
    try {
      if (action === 'activate') await activateCampaign(id)
      if (action === 'pause') await pauseCampaign(id)
      if (action === 'resume') await resumeCampaign(id)
      if (action === 'cancel') await cancelCampaign(id)
      toast({ title: `Campaign ${action}d`, type: 'success' })
      await load()
    } catch (err) {
      toast({
        title: 'Action failed',
        description: err instanceof ApiError ? err.message : 'Unknown error',
        type: 'error',
      })
    } finally {
      setBusy(false)
    }
  }

  if (loading || !campaign) {
    return (
      <div className="min-w-0">
        <PageHeader title="Campaign" description="Loading…" />
        <Card>
          <CardContent className="py-10 text-sm text-muted-foreground">Loading campaign…</CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-w-0 space-y-6">
      <PageHeader
        title={campaign.name}
        description={campaign.description || 'Campaign detail and progress'}
        breadcrumbs={[
          { label: 'Outreach' },
          { label: 'Campaigns' },
          { label: campaign.name },
        ]}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => navigate('/campaigns')}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                await processDueCampaigns()
                await load()
                toast({ title: 'Processed due sends', type: 'success' })
              }}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Process due
            </Button>
            {campaign.status === 'draft' && (
              <Button size="sm" disabled={busy} onClick={() => void runAction('activate')}>
                <Play className="mr-2 h-4 w-4" />
                Activate
              </Button>
            )}
            {campaign.status === 'active' && (
              <Button size="sm" variant="outline" disabled={busy} onClick={() => void runAction('pause')}>
                <Pause className="mr-2 h-4 w-4" />
                Pause
              </Button>
            )}
            {campaign.status === 'paused' && (
              <Button size="sm" disabled={busy} onClick={() => void runAction('resume')}>
                <Play className="mr-2 h-4 w-4" />
                Resume
              </Button>
            )}
            {campaign.status !== 'cancelled' && campaign.status !== 'completed' && (
              <Button size="sm" variant="outline" disabled={busy} onClick={() => void runAction('cancel')}>
                <XCircle className="mr-2 h-4 w-4" />
                Cancel
              </Button>
            )}
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={statusVariant(campaign.status)}>{campaign.status}</Badge>
        <span className="text-sm text-muted-foreground">
          {campaign.timezone} · {campaign.send_start_hour}:00–{campaign.send_end_hour}:00 ·{' '}
          {campaign.hourly_send_limit}/hr · {campaign.daily_send_limit}/day
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ['Recipients', analytics?.recipients ?? 0],
          ['Sent', analytics?.sent ?? 0],
          ['Delivered', analytics?.has_send_data ? analytics.delivered : '—'],
          ['Replied', analytics?.replied ?? 0],
          ['Bounced', analytics?.bounced ?? 0],
          ['Unsubscribed', analytics?.unsubscribed ?? 0],
          ['Failed', analytics?.failed ?? 0],
          ['Completed', analytics?.completed ?? 0],
        ].map(([label, value]) => (
          <Card key={String(label)}>
            <CardHeader className="pb-2">
              <CardDescription>{label}</CardDescription>
              <CardTitle className="text-2xl">{value}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Rates</CardTitle>
          <CardDescription>
            {analytics?.reply_detection_note || 'Reply detection provider not configured'}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <p>Delivery: {formatRate(analytics?.delivery_rate)}</p>
          <p>Reply: {formatRate(analytics?.reply_rate)}</p>
          <p>Bounce: {formatRate(analytics?.bounce_rate)}</p>
          <p>Unsubscribe: {formatRate(analytics?.unsubscribe_rate)}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sequence</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {steps.length === 0 ? (
            <p className="text-sm text-muted-foreground">No steps configured.</p>
          ) : (
            steps.map((s) => (
              <div key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm">
                <span className="font-medium">Step {s.step_number}</span>
                <span className="text-muted-foreground">{s.type}</span>
                <span>
                  {s.step_number === 1
                    ? 'Send immediately (within window)'
                    : `Wait ${Math.round(s.delay_minutes / (24 * 60))} day(s)`}
                </span>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recipients</CardTitle>
          <CardDescription>{recipients.length} enrolled</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {recipients.length === 0 ? (
            <p className="text-sm text-muted-foreground">No recipients enrolled yet.</p>
          ) : (
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="pb-3 pr-3 font-medium">Business</th>
                  <th className="pb-3 pr-3 font-medium">Email</th>
                  <th className="pb-3 pr-3 font-medium">Step</th>
                  <th className="pb-3 pr-3 font-medium">Status</th>
                  <th className="pb-3 pr-3 font-medium">Next action</th>
                  <th className="pb-3 font-medium">Last sent</th>
                </tr>
              </thead>
              <tbody>
                {recipients.map((r) => (
                  <tr key={r.id} className="border-b last:border-0">
                    <td className="py-3 pr-3">
                      <Link className="text-primary hover:underline" to={`/leads/${r.lead_id}`}>
                        {r.business_name || r.lead_id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="py-3 pr-3">{r.email || '—'}</td>
                    <td className="py-3 pr-3">{r.current_step}</td>
                    <td className="py-3 pr-3">
                      <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
                    </td>
                    <td className="py-3 pr-3">{formatWhen(r.next_action_at)}</td>
                    <td className="py-3">{formatWhen(r.last_sent_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
