import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Megaphone, Plus, Pause, Play, XCircle, Eye, RefreshCw } from 'lucide-react'
import { PageHeader } from '@/components/shared/PageHeader'
import { EmptyState } from '@/components/shared/EmptyState'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/shared/Toast'
import { ApiError } from '@/api/client'
import {
  activateCampaign,
  cancelCampaign,
  listCampaigns,
  pauseCampaign,
  processDueCampaigns,
  resumeCampaign,
  type ApiCampaign,
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
      return 'destructive'
    case 'completed':
      return 'secondary'
    default:
      return 'outline'
  }
}

export function CampaignsPage() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [loading, setLoading] = useState(true)
  const [campaigns, setCampaigns] = useState<ApiCampaign[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setCampaigns(await listCampaigns())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load campaigns')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function runAction(id: string, action: 'activate' | 'pause' | 'resume' | 'cancel') {
    setBusyId(id)
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
      setBusyId(null)
    }
  }

  async function tickScheduler() {
    try {
      const result = await processDueCampaigns()
      toast({
        title: 'Scheduler ran',
        description: `Processed ${result.processed} due recipient(s)`,
        type: 'success',
      })
      await load()
    } catch (err) {
      toast({
        title: 'Scheduler failed',
        description: err instanceof ApiError ? err.message : 'Unknown error',
        type: 'error',
      })
    }
  }

  return (
    <div className="min-w-0 space-y-6">
      <PageHeader
        title="Outreach Campaigns"
        description="Create sequences, enroll verified leads, and schedule follow-ups."
        breadcrumbs={[{ label: 'Outreach' }, { label: 'Campaigns' }]}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => void tickScheduler()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Process due
            </Button>
            <Button size="sm" onClick={() => navigate('/campaigns/new')}>
              <Plus className="mr-2 h-4 w-4" />
              Create campaign
            </Button>
          </div>
        }
      />

      {error && (
        <Card>
          <CardContent className="py-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      )}

      {loading ? (
        <Card>
          <CardContent className="py-10 text-sm text-muted-foreground">Loading campaigns…</CardContent>
        </Card>
      ) : campaigns.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No campaigns yet</CardTitle>
            <CardDescription>
              Build an email sequence, select verified leads with approved drafts, then activate.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={Megaphone}
              title="Create your first campaign"
              description="Enrollment is always explicit. Reply detection provider is not configured yet."
              actionLabel="Create campaign"
              onAction={() => navigate('/campaigns/new')}
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Campaigns</CardTitle>
            <CardDescription>
              Metrics reflect real send data only. Reply detection provider not configured.
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="pb-3 pr-3 font-medium">Name</th>
                  <th className="pb-3 pr-3 font-medium">Status</th>
                  <th className="pb-3 pr-3 font-medium">Recipients</th>
                  <th className="pb-3 pr-3 font-medium">Active</th>
                  <th className="pb-3 pr-3 font-medium">Replied</th>
                  <th className="pb-3 pr-3 font-medium">Sent</th>
                  <th className="pb-3 pr-3 font-medium">Delivered</th>
                  <th className="pb-3 pr-3 font-medium">Bounced</th>
                  <th className="pb-3 pr-3 font-medium">Completed</th>
                  <th className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr key={c.id} className="border-b last:border-0">
                    <td className="py-3 pr-3">
                      <Link className="font-medium text-primary hover:underline" to={`/campaigns/${c.id}`}>
                        {c.name}
                      </Link>
                    </td>
                    <td className="py-3 pr-3">
                      <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
                    </td>
                    <td className="py-3 pr-3">{c.recipients_count ?? 0}</td>
                    <td className="py-3 pr-3">{c.active_count ?? 0}</td>
                    <td className="py-3 pr-3">{c.replied_count ?? 0}</td>
                    <td className="py-3 pr-3">{c.sent_count ?? 0}</td>
                    <td className="py-3 pr-3">{c.delivered_count ?? 0}</td>
                    <td className="py-3 pr-3">{c.bounced_count ?? 0}</td>
                    <td className="py-3 pr-3">{c.completed_count ?? 0}</td>
                    <td className="py-3">
                      <div className="flex flex-wrap gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => navigate(`/campaigns/${c.id}`)}
                          aria-label="View"
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        {c.status === 'draft' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={busyId === c.id}
                            onClick={() => void runAction(c.id, 'activate')}
                            aria-label="Activate"
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                        )}
                        {c.status === 'active' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={busyId === c.id}
                            onClick={() => void runAction(c.id, 'pause')}
                            aria-label="Pause"
                          >
                            <Pause className="h-4 w-4" />
                          </Button>
                        )}
                        {c.status === 'paused' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={busyId === c.id}
                            onClick={() => void runAction(c.id, 'resume')}
                            aria-label="Resume"
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                        )}
                        {c.status !== 'cancelled' && c.status !== 'completed' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={busyId === c.id}
                            onClick={() => void runAction(c.id, 'cancel')}
                            aria-label="Cancel"
                          >
                            <XCircle className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
