import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/shared/PageHeader'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/components/shared/Toast'
import { ApiError } from '@/api/client'
import {
  formatPct,
  getPipelineBoard,
  getPipelineStats,
  updateLeadPipeline,
  type PipelineBoard,
  type PipelineStats,
} from '@/api/meetings'

const STAGE_LABELS: Record<string, string> = {
  new: 'New',
  qualified: 'Qualified',
  contacted: 'Contacted',
  replied: 'Replied',
  meeting_requested: 'Meeting Requested',
  meeting_scheduled: 'Meeting Scheduled',
  meeting_completed: 'Meeting Completed',
  proposal: 'Proposal',
  won: 'Won',
  lost: 'Lost',
}

export function PipelinePage() {
  const { toast } = useToast()
  const [board, setBoard] = useState<PipelineBoard | null>(null)
  const [stats, setStats] = useState<PipelineStats | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [b, s] = await Promise.all([getPipelineBoard(), getPipelineStats()])
      setBoard(b)
      setStats(s)
    } catch (err) {
      toast({
        title: 'Failed to load pipeline',
        description: err instanceof ApiError ? err.message : 'Unknown error',
        type: 'error',
      })
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    void load()
  }, [load])

  async function changeStage(leadId: string, stage: string) {
    try {
      await updateLeadPipeline(leadId, stage, 'Manual board update')
      toast({ title: 'Stage updated', type: 'success' })
      await load()
    } catch (err) {
      toast({
        title: 'Update failed',
        description: err instanceof ApiError ? err.message : 'Unknown error',
        type: 'error',
      })
    }
  }

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title="Sales Pipeline"
        description="CRM stages from discovery through meetings. Won/lost are manual only."
        breadcrumbs={[{ label: 'Management' }, { label: 'Pipeline' }]}
      />

      {stats?.has_real_data ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total leads</CardDescription>
              <CardTitle>{stats.total_leads}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Meeting requests</CardDescription>
              <CardTitle>{stats.meeting_requested}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Booking rate</CardDescription>
              <CardTitle>{formatPct(stats.booking_rate)}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Win rate</CardDescription>
              <CardTitle>{formatPct(stats.win_rate)}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No pipeline analytics yet.</p>
      )}

      {loading || !board ? (
        <Card>
          <CardContent className="py-10 text-sm text-muted-foreground">Loading board…</CardContent>
        </Card>
      ) : (
        <div className="-mx-3 overflow-x-auto px-3">
          <div className="flex min-w-max gap-3 pb-2">
            {board.stages.map((stage) => (
              <div key={stage} className="w-[240px] shrink-0 rounded-xl border bg-card">
                <div className="border-b px-3 py-2">
                  <p className="text-sm font-medium">{STAGE_LABELS[stage] || stage}</p>
                  <p className="text-xs text-muted-foreground">{board.columns[stage]?.length || 0}</p>
                </div>
                <div className="max-h-[60dvh] space-y-2 overflow-y-auto p-2">
                  {(board.columns[stage] || []).map((lead) => (
                    <div key={lead.id} className="rounded-lg border p-2 text-sm">
                      <Link className="font-medium text-primary hover:underline" to={`/leads/${lead.id}`}>
                        {lead.company_name}
                      </Link>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {lead.priority ? <Badge variant="outline">{lead.priority}</Badge> : null}
                        {lead.lead_score != null ? (
                          <Badge variant="secondary">Score {lead.lead_score}</Badge>
                        ) : null}
                      </div>
                      <Select value={stage} onValueChange={(v) => void changeStage(lead.id, v)}>
                        <SelectTrigger className="mt-2 h-8 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {board.stages.map((s) => (
                            <SelectItem key={s} value={s}>
                              {STAGE_LABELS[s] || s}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        No revenue metrics. Calendar live: {board?.calendar_live ? 'yes' : 'no'}.
      </p>
    </div>
  )
}
