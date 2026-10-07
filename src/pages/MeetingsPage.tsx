import { useCallback, useEffect, useMemo, useState } from 'react'
import { CalendarDays, Check, XCircle, UserX } from 'lucide-react'
import { PageHeader } from '@/components/shared/PageHeader'
import { EmptyState } from '@/components/shared/EmptyState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/components/shared/Toast'
import { ApiError } from '@/api/client'
import {
  cancelMeeting,
  completeMeeting,
  getCalendarStatus,
  listMeetings,
  noShowMeeting,
  type ApiMeeting,
} from '@/api/meetings'

function formatWhen(iso: string, tz: string) {
  try {
    return new Date(iso).toLocaleString(undefined, { timeZone: tz === 'UTC' ? 'UTC' : undefined })
  } catch {
    return iso
  }
}

export function MeetingsPage() {
  const { toast } = useToast()
  const [filter, setFilter] = useState('upcoming')
  const [meetings, setMeetings] = useState<ApiMeeting[]>([])
  const [loading, setLoading] = useState(true)
  const [calendarNote, setCalendarNote] = useState('Calendar provider: Not configured')
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [rows, cal] = await Promise.all([
        listMeetings(filter === 'all' ? undefined : filter),
        getCalendarStatus().catch(() => null),
      ])
      setMeetings(rows)
      if (cal) {
        setCalendarNote(
          cal.calendar_live
            ? `Calendar: ${cal.provider} (live)`
            : `Calendar provider: ${cal.configured ? cal.provider + ' (mock/not live)' : 'Not configured'}`,
        )
      }
    } catch (err) {
      toast({
        title: 'Failed to load meetings',
        description: err instanceof ApiError ? err.message : 'Unknown error',
        type: 'error',
      })
    } finally {
      setLoading(false)
    }
  }, [filter, toast])

  useEffect(() => {
    void load()
  }, [load])

  const counts = useMemo(() => {
    return {
      total: meetings.length,
    }
  }, [meetings])

  async function act(id: string, action: 'cancel' | 'complete' | 'no_show') {
    setBusy(id)
    try {
      if (action === 'cancel') await cancelMeeting(id)
      if (action === 'complete') await completeMeeting(id, 'unknown')
      if (action === 'no_show') await noShowMeeting(id)
      toast({ title: `Meeting ${action.replace('_', ' ')}`, type: 'success' })
      await load()
    } catch (err) {
      toast({
        title: 'Action failed',
        description: err instanceof ApiError ? err.message : 'Unknown error',
        type: 'error',
      })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        title="Meetings"
        description="Schedule and manage discovery calls. AI never auto-books."
        breadcrumbs={[{ label: 'Management' }, { label: 'Meetings' }]}
        actions={
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="upcoming">Upcoming</SelectItem>
              <SelectItem value="today">Today</SelectItem>
              <SelectItem value="week">This Week</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
              <SelectItem value="no_show">No Show</SelectItem>
              <SelectItem value="all">All</SelectItem>
            </SelectContent>
          </Select>
        }
      />

      <p className="text-sm text-muted-foreground">{calendarNote}</p>

      {loading ? (
        <Card>
          <CardContent className="py-10 text-sm text-muted-foreground">Loading meetings…</CardContent>
        </Card>
      ) : meetings.length === 0 ? (
        <EmptyState
          icon={CalendarDays}
          title="No meetings"
          description="Create a meeting type and availability in Settings, then share a booking link from a meeting-requested conversation."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {meetings.map((m) => (
            <Card key={m.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base">{m.business_name || m.prospect_name || m.title}</CardTitle>
                  <Badge variant="outline">{m.status}</Badge>
                </div>
                <CardDescription>
                  {m.meeting_type_name || m.title} · {m.timezone}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p>{formatWhen(m.start_at, m.timezone)}</p>
                <p className="text-muted-foreground">{m.prospect_email || '—'}</p>
                {m.meeting_url ? (
                  <a className="text-primary underline" href={m.meeting_url} target="_blank" rel="noreferrer">
                    Meeting link
                  </a>
                ) : (
                  <p className="text-xs text-muted-foreground">No meeting URL (calendar not live)</p>
                )}
                {m.status === 'scheduled' || m.status === 'confirmed' || m.status === 'rescheduled' ? (
                  <div className="flex flex-wrap gap-1">
                    <Button size="sm" variant="outline" disabled={busy === m.id} onClick={() => void act(m.id, 'complete')}>
                      <Check className="mr-1 h-3 w-3" />
                      Complete
                    </Button>
                    <Button size="sm" variant="outline" disabled={busy === m.id} onClick={() => void act(m.id, 'no_show')}>
                      <UserX className="mr-1 h-3 w-3" />
                      No show
                    </Button>
                    <Button size="sm" variant="outline" disabled={busy === m.id} onClick={() => void act(m.id, 'cancel')}>
                      <XCircle className="mr-1 h-3 w-3" />
                      Cancel
                    </Button>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <p className="text-xs text-muted-foreground">{counts.total} shown</p>
    </div>
  )
}
