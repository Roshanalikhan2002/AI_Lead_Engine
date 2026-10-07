import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageHeader } from '@/components/shared/PageHeader'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useToast } from '@/components/shared/Toast'
import { ApiError } from '@/api/client'
import { createCampaign, enrollBatch, type CampaignStepInput } from '@/api/campaigns'

const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Berlin',
  'Asia/Karachi',
  'Asia/Dubai',
  'Asia/Singapore',
]

export function CampaignCreatePage() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [step, setStep] = useState(1)
  const [saving, setSaving] = useState(false)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [timezone, setTimezone] = useState('America/New_York')
  const [sendStart, setSendStart] = useState(9)
  const [sendEnd, setSendEnd] = useState(17)
  const [dailyLimit, setDailyLimit] = useState(50)
  const [hourlyLimit, setHourlyLimit] = useState(10)
  const [weekends, setWeekends] = useState(false)

  const [priority, setPriority] = useState<'none' | 'hot' | 'warm'>('none')
  const [minScore, setMinScore] = useState(70)
  const [useScore, setUseScore] = useState(true)
  const [primaryService, setPrimaryService] = useState('')

  const [steps, setSteps] = useState<CampaignStepInput[]>([
    { step_number: 1, type: 'email', delay_minutes: 0 },
    { step_number: 2, type: 'email', delay_minutes: 3 * 24 * 60 },
    { step_number: 3, type: 'email', delay_minutes: 5 * 24 * 60 },
  ])

  const estimatedDays = useMemo(() => {
    const delays = steps.map((s) => s.delay_minutes)
    const totalMinutes = delays.reduce((a, b) => a + b, 0)
    return Math.ceil(totalMinutes / (60 * 24))
  }, [steps])

  function updateStepDelay(index: number, days: number) {
    setSteps((prev) =>
      prev.map((s, i) =>
        i === index
          ? { ...s, delay_minutes: i === 0 ? 0 : Math.max(0, Math.round(days * 24 * 60)) }
          : s,
      ),
    )
  }

  async function handleCreate() {
    if (!name.trim()) {
      toast({ title: 'Name required', type: 'warning' })
      return
    }
    setSaving(true)
    try {
      const campaign = await createCampaign({
        name: name.trim(),
        description: description.trim() || null,
        timezone,
        send_start_hour: sendStart,
        send_end_hour: sendEnd,
        daily_send_limit: dailyLimit,
        hourly_send_limit: hourlyLimit,
        send_on_weekends: weekends,
        steps,
      })

      const filters: {
        min_score?: number
        priority?: string
        primary_service?: string
      } = {}
      if (useScore) filters.min_score = minScore
      if (priority !== 'none') filters.priority = priority
      if (primaryService.trim()) filters.primary_service = primaryService.trim()

      let enrolledCount = 0
      if (Object.keys(filters).length > 0) {
        const batch = await enrollBatch(campaign.id, filters)
        enrolledCount = batch.enrolled_count
      }

      toast({
        title: 'Campaign created',
        description:
          enrolledCount > 0
            ? `Enrolled ${enrolledCount} recipient(s). Activate when ready.`
            : 'No recipients enrolled yet — add filters or enroll from the detail page.',
        type: 'success',
      })
      navigate(`/campaigns/${campaign.id}`)
    } catch (err) {
      toast({
        title: 'Create failed',
        description: err instanceof ApiError ? err.message : 'Unknown error',
        type: 'error',
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-w-0 space-y-6">
      <PageHeader
        title="Create campaign"
        description="Configure details, select recipients, build a sequence, then review."
        breadcrumbs={[
          { label: 'Outreach' },
          { label: 'Campaigns' },
          { label: 'Create' },
        ]}
      />

      <div className="flex flex-wrap gap-2 text-sm">
        {[1, 2, 3, 4].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => setStep(n)}
            className={`rounded-lg px-3 py-1.5 ${
              step === n ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
            }`}
          >
            Step {n}
          </button>
        ))}
      </div>

      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Campaign details</CardTitle>
            <CardDescription>Name, timezone, sending window, and limits.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2 space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="sm:col-span-2 space-y-2">
              <Label htmlFor="desc">Description</Label>
              <Textarea id="desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
            </div>
            <div className="space-y-2">
              <Label>Timezone</Label>
              <Select value={timezone} onValueChange={setTimezone}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TIMEZONES.map((tz) => (
                    <SelectItem key={tz} value={tz}>
                      {tz}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between rounded-lg border px-3 py-2">
              <div>
                <Label>Send on weekends</Label>
                <p className="text-xs text-muted-foreground">Default off</p>
              </div>
              <Switch checked={weekends} onCheckedChange={setWeekends} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="start">Send start hour</Label>
              <Input
                id="start"
                type="number"
                min={0}
                max={23}
                value={sendStart}
                onChange={(e) => setSendStart(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="end">Send end hour</Label>
              <Input
                id="end"
                type="number"
                min={1}
                max={24}
                value={sendEnd}
                onChange={(e) => setSendEnd(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="daily">Daily send limit</Label>
              <Input
                id="daily"
                type="number"
                min={1}
                value={dailyLimit}
                onChange={(e) => setDailyLimit(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="hourly">Hourly send limit</Label>
              <Input
                id="hourly"
                type="number"
                min={1}
                value={hourlyLimit}
                onChange={(e) => setHourlyLimit(Number(e.target.value))}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {step === 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Select recipients</CardTitle>
            <CardDescription>
              Enrollment is explicit via filters. Only verified emails with approved drafts are enrolled.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Priority</Label>
              <Select value={priority} onValueChange={(v) => setPriority(v as typeof priority)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Any / skip priority filter</SelectItem>
                  <SelectItem value="hot">Hot leads</SelectItem>
                  <SelectItem value="warm">Warm leads</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="service">Primary service (optional)</Label>
              <Input
                id="service"
                placeholder="e.g. appointment_automation"
                value={primaryService}
                onChange={(e) => setPrimaryService(e.target.value)}
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border px-3 py-2 sm:col-span-2">
              <div>
                <Label>Score threshold</Label>
                <p className="text-xs text-muted-foreground">AI score ≥ threshold</p>
              </div>
              <Switch checked={useScore} onCheckedChange={setUseScore} />
            </div>
            {useScore && (
              <div className="space-y-2">
                <Label htmlFor="score">Minimum score</Label>
                <Input
                  id="score"
                  type="number"
                  min={0}
                  max={100}
                  value={minScore}
                  onChange={(e) => setMinScore(Number(e.target.value))}
                />
              </div>
            )}
            <p className="sm:col-span-2 text-xs text-muted-foreground">
              Verified emails and approved drafts are always required at enrollment time.
            </p>
          </CardContent>
        </Card>
      )}

      {step === 3 && (
        <Card>
          <CardHeader>
            <CardTitle>Build sequence</CardTitle>
            <CardDescription>
              Each step sends the recipient&apos;s approved outreach draft. Delays are after the previous step.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {steps.map((s, index) => (
              <div key={s.step_number} className="grid gap-3 rounded-lg border p-4 sm:grid-cols-3">
                <div>
                  <p className="font-medium">Step {s.step_number}</p>
                  <p className="text-xs text-muted-foreground">
                    {index === 0 ? 'Initial email' : index === steps.length - 1 ? 'Final follow-up' : 'Follow-up'}
                  </p>
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label>Wait (days after previous)</Label>
                  <Input
                    type="number"
                    min={0}
                    disabled={index === 0}
                    value={index === 0 ? 0 : Math.round(s.delay_minutes / (24 * 60))}
                    onChange={(e) => updateStepDelay(index, Number(e.target.value))}
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {step === 4 && (
        <Card>
          <CardHeader>
            <CardTitle>Review</CardTitle>
            <CardDescription>Confirm settings before creating.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>
              <span className="text-muted-foreground">Name:</span> {name || '—'}
            </p>
            <p>
              <span className="text-muted-foreground">Timezone:</span> {timezone}
            </p>
            <p>
              <span className="text-muted-foreground">Window:</span> {sendStart}:00–{sendEnd}:00
              {weekends ? ' (includes weekends)' : ' (weekdays only)'}
            </p>
            <p>
              <span className="text-muted-foreground">Limits:</span> {hourlyLimit}/hour, {dailyLimit}/day
            </p>
            <p>
              <span className="text-muted-foreground">Steps:</span> {steps.length}
            </p>
            <p>
              <span className="text-muted-foreground">Estimated sequence span:</span> ~{estimatedDays} day(s)
            </p>
            <p className="text-muted-foreground">
              Recipients will be enrolled from filters if provided. Campaign starts in draft — activate from the
              detail page when ready.
            </p>
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap justify-between gap-2">
        <Button variant="outline" onClick={() => (step > 1 ? setStep(step - 1) : navigate('/campaigns'))}>
          {step > 1 ? 'Back' : 'Cancel'}
        </Button>
        {step < 4 ? (
          <Button onClick={() => setStep(step + 1)}>Continue</Button>
        ) : (
          <Button disabled={saving} onClick={() => void handleCreate()}>
            {saving ? 'Creating…' : 'Create campaign'}
          </Button>
        )}
      </div>
    </div>
  )
}
