import { useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useTheme } from '@/hooks/useTheme'
import { useToast } from '@/components/shared/Toast'
import { cn } from '@/lib/utils'
import {
  createAvailability,
  createMeetingType,
  getCalendarStatus,
  listAvailability,
  listMeetingTypes,
  type AvailabilityRule,
  type MeetingType,
} from '@/api/meetings'
import { getSystemHealth, testProvider, type SystemHealthResponse, getReadiness, validateConfig, getProviderLogs, getSystemJobs, getSystemAudit, getProviderMatrix, type ReadinessResponse, type ConfigValidateResponse, type ProviderMatrixRow } from '@/api/system'
import { inviteTeamMember, listTeam } from '@/api/auth'
import { ApiError } from '@/api/client'
import { useAuth } from '@/hooks/useAuth'
import {
  cancelSubscription,
  changePlan,
  getBillingSubscription,
  getBillingUsage,
  openBillingPortal,
  resumeSubscription,
  startCheckout,
  type SubscriptionInfo,
  type UsageResponse,
} from '@/api/billing'
import { Link, useSearchParams } from 'react-router-dom'
import { Progress } from '@/components/ui/progress'

export function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const { toast } = useToast()
  const [confidence, setConfidence] = useState([75])
  const [autoQualify, setAutoQualify] = useState(true)
  const [aiPersonalize, setAiPersonalize] = useState(true)
  const [searchParams] = useSearchParams()
  const initialTab = searchParams.get('tab') || 'profile'

  return (
    <div className="min-w-0">
      <PageHeader
        title="Settings"
        description="Configure workspace, AI behavior, and appearance."
        breadcrumbs={[{ label: 'Management' }, { label: 'Settings' }]}
      />

      <Tabs defaultValue={initialTab} className="w-full">
        <TabsList className="mb-2 w-full justify-start overflow-x-auto">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="workspace">Workspace</TabsTrigger>
          <TabsTrigger value="leadgen">Lead Generation</TabsTrigger>
          <TabsTrigger value="ai">AI Settings</TabsTrigger>
          <TabsTrigger value="email">Email Settings</TabsTrigger>
          <TabsTrigger value="meetings">Meetings</TabsTrigger>
          <TabsTrigger value="team">Team</TabsTrigger>
          <TabsTrigger value="billing">Usage & Billing</TabsTrigger>
          <TabsTrigger value="system">System Health</TabsTrigger>
          <TabsTrigger value="readiness">Production Readiness</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="appearance">Appearance</TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>Profile</CardTitle>
              <CardDescription>Your personal account details</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <Field label="Full name">
                <Input defaultValue="Roshan" />
              </Field>
              <Field label="Email">
                <Input defaultValue="roshan@leadflow.ai" />
              </Field>
              <Field label="Job title">
                <Input defaultValue="Agency Admin" />
              </Field>
              <Field label="Timezone">
                <Select defaultValue="asia-karachi">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="asia-karachi">Asia/Karachi</SelectItem>
                    <SelectItem value="utc">UTC</SelectItem>
                    <SelectItem value="america-new-york">America/New_York</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <div className="sm:col-span-2">
                <Button onClick={() => toast({ title: 'Profile saved (demo)', type: 'success' })}>Save changes</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="workspace">
          <Card>
            <CardHeader>
              <CardTitle>Workspace</CardTitle>
              <CardDescription>Organization-level preferences</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <Field label="Workspace name">
                <Input defaultValue="LeadFlow Agency" />
              </Field>
              <Field label="Default currency">
                <Select defaultValue="usd">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="usd">USD</SelectItem>
                    <SelectItem value="gbp">GBP</SelectItem>
                    <SelectItem value="eur">EUR</SelectItem>
                    <SelectItem value="aed">AED</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <div className="sm:col-span-2">
                <Button onClick={() => toast({ title: 'Workspace updated (demo)', type: 'success' })}>Save workspace</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="leadgen">
          <Card>
            <CardHeader>
              <CardTitle>Lead Generation</CardTitle>
              <CardDescription>Defaults for discovery runs</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="Default country">
                <Select defaultValue="USA">
                  <SelectTrigger className="max-w-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="USA">USA</SelectItem>
                    <SelectItem value="Canada">Canada</SelectItem>
                    <SelectItem value="UK">UK</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Default quantity">
                <Input type="number" defaultValue={250} className="max-w-sm" />
              </Field>
              <Button onClick={() => toast({ title: 'Lead gen defaults saved', type: 'success' })}>Save</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ai">
          <Card>
            <CardHeader>
              <CardTitle>AI Settings</CardTitle>
              <CardDescription>Tune qualification and personalization behavior</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <Field label="Model">
                <Select defaultValue="leadflow-pro">
                  <SelectTrigger className="max-w-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="leadflow-pro">LeadFlow Pro</SelectItem>
                    <SelectItem value="leadflow-fast">LeadFlow Fast</SelectItem>
                    <SelectItem value="leadflow-max">LeadFlow Max</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <div className="max-w-md space-y-3">
                <div className="flex items-center justify-between">
                  <Label>AI confidence threshold</Label>
                  <span className="text-sm font-medium tabular-nums">{confidence[0]}%</span>
                </div>
                <Slider value={confidence} onValueChange={setConfidence} min={50} max={95} step={1} />
              </div>
              <ToggleRow
                label="Auto qualification"
                description="Automatically qualify leads above the confidence threshold"
                checked={autoQualify}
                onCheckedChange={setAutoQualify}
              />
              <ToggleRow
                label="AI email personalization"
                description="Personalize outreach copy using website and business signals"
                checked={aiPersonalize}
                onCheckedChange={setAiPersonalize}
              />
              <Button onClick={() => toast({ title: 'AI settings saved (demo)', type: 'success' })}>Save AI settings</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="email">
          <Card>
            <CardHeader>
              <CardTitle>Email Settings</CardTitle>
              <CardDescription>Sender identity and delivery preferences</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <Field label="Default sender name">
                <Input defaultValue="Roshan" />
              </Field>
              <Field label="Default sender email">
                <Input defaultValue="roshan@leadflow.ai" />
              </Field>
              <Field label="Reply-to">
                <Input defaultValue="roshan@leadflow.ai" />
              </Field>
              <div className="sm:col-span-2">
                <Button onClick={() => toast({ title: 'Email settings saved', type: 'success' })}>Save</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="meetings">
          <MeetingsSettingsPanel />
        </TabsContent>

        <TabsContent value="team">
          <TeamSettingsPanel />
        </TabsContent>

        <TabsContent value="billing">
          <BillingSettingsPanel />
        </TabsContent>

        <TabsContent value="system">
          <SystemHealthPanel />
        </TabsContent>

        <TabsContent value="readiness">
          <ProductionReadinessPanel />
        </TabsContent>

        <TabsContent value="notifications">
          <Card>
            <CardHeader>
              <CardTitle>Notifications</CardTitle>
              <CardDescription>Choose what you want to be notified about</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <ToggleRow label="New replies" description="When a prospect responds" checked={true} onCheckedChange={() => undefined} />
              <ToggleRow label="Meeting reminders" description="30 minutes before scheduled calls" checked={true} onCheckedChange={() => undefined} />
              <ToggleRow label="Lead generation complete" description="When a discovery run finishes" checked={true} onCheckedChange={() => undefined} />
              <ToggleRow label="Weekly digest" description="Summary of pipeline performance" checked={false} onCheckedChange={() => undefined} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="appearance">
          <Card>
            <CardHeader>
              <CardTitle>Appearance</CardTitle>
              <CardDescription>Light, dark, or follow system preference</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 sm:grid-cols-3">
                {([
                  { id: 'light', label: 'Light', desc: 'Clean bright interface' },
                  { id: 'dark', label: 'Dark', desc: 'Easy on the eyes' },
                  { id: 'system', label: 'System', desc: 'Match device setting' },
                ] as const).map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setTheme(option.id)}
                    className={cn(
                      'rounded-xl border p-4 text-left transition-all',
                      theme === option.id ? 'border-primary bg-primary/5 shadow-sm' : 'border-border hover:bg-muted/40',
                    )}
                  >
                    <p className="font-medium">{option.label}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{option.desc}</p>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function BillingSettingsPanel() {
  const { toast } = useToast()
  const { hasPermission } = useAuth()
  const [searchParams] = useSearchParams()
  const [usage, setUsage] = useState<UsageResponse | null>(null)
  const [sub, setSub] = useState<SubscriptionInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const canManage = hasPermission('billing.manage')
  const canView = hasPermission('billing.view')
  const upgradePlan = searchParams.get('upgrade')

  const refresh = async () => {
    if (!canView) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const [u, s] = await Promise.all([getBillingUsage(), getBillingSubscription()])
      setUsage(u)
      setSub(s)
    } catch (err) {
      toast({
        title: 'Failed to load billing',
        description: err instanceof ApiError ? err.message : 'Unknown error',
        type: 'error',
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canView])

  useEffect(() => {
    if (!upgradePlan || !canManage || !sub?.billing_provider_configured) return
    void (async () => {
      try {
        if (sub.billing_provider_name === 'mock') {
          await changePlan(upgradePlan)
          toast({ title: 'Plan updated (mock)', type: 'success' })
          await refresh()
        } else {
          const res = await startCheckout(upgradePlan)
          if (res.checkout_url) {
            if (res.checkout_url.startsWith('mock://')) {
              toast({
                title: 'Mock checkout',
                description: res.message,
                type: 'success',
              })
            } else {
              window.location.href = res.checkout_url
            }
          } else {
            toast({ title: 'Checkout unavailable', description: res.message, type: 'error' })
          }
        }
      } catch (err) {
        toast({
          title: 'Upgrade failed',
          description: err instanceof ApiError ? err.message : 'Error',
          type: 'error',
        })
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [upgradePlan])

  if (!canView) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Usage & Billing</CardTitle>
          <CardDescription>Only owners and admins can view billing settings.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const configured = Boolean(sub?.billing_provider_configured)

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Current plan</CardTitle>
          <CardDescription>
            {sub?.plan_name || usage?.plan_name || 'Free'} · Status: {sub?.status || 'active'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p>
            Billing period:{' '}
            {usage?.period_start ? new Date(usage.period_start).toLocaleDateString() : '—'} →{' '}
            {usage?.period_end ? new Date(usage.period_end).toLocaleDateString() : '—'}
          </p>
          <p>
            Renewal:{' '}
            {sub?.current_period_end
              ? new Date(sub.current_period_end).toLocaleDateString()
              : 'N/A (free / no provider period)'}
          </p>
          {sub?.cancel_at_period_end && (
            <p className="text-amber-700">Cancellation scheduled at period end.</p>
          )}
          {sub?.grace_warning && (
            <p className="text-amber-700">
              Payment issue — grace period until{' '}
              {sub.grace_period_ends_at
                ? new Date(sub.grace_period_ends_at).toLocaleDateString()
                : 'soon'}
              .
            </p>
          )}
          {!configured && (
            <p className="rounded-lg border border-border bg-muted/40 px-3 py-2">
              Billing provider is not configured. Free plan works without Stripe. Paid checkout and
              portal actions are disabled.
            </p>
          )}
          <div className="flex flex-wrap gap-2 pt-2">
            <Button asChild variant="outline" size="sm">
              <Link to="/pricing">View plans</Link>
            </Button>
            {canManage && (
              <>
                <Button
                  size="sm"
                  disabled={!configured}
                  onClick={async () => {
                    try {
                      const res = await startCheckout('starter')
                      toast({
                        title: res.mode === 'mock' ? 'Mock checkout' : 'Checkout',
                        description: res.checkout_url || res.message,
                        type: res.checkout_url ? 'success' : 'error',
                      })
                    } catch (err) {
                      toast({
                        title: 'Checkout failed',
                        description: err instanceof ApiError ? err.message : 'Error',
                        type: 'error',
                      })
                    }
                  }}
                >
                  Upgrade
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!configured}
                  onClick={async () => {
                    try {
                      const res = await openBillingPortal()
                      toast({
                        title: res.mode === 'mock' ? 'Mock portal' : 'Portal',
                        description: res.portal_url || res.message,
                        type: res.portal_url ? 'success' : 'error',
                      })
                    } catch (err) {
                      toast({
                        title: 'Portal unavailable',
                        description: err instanceof ApiError ? err.message : 'Error',
                        type: 'error',
                      })
                    }
                  }}
                >
                  Manage Billing
                </Button>
                {sub?.cancel_at_period_end ? (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!canManage}
                    onClick={async () => {
                      try {
                        await resumeSubscription()
                        toast({ title: 'Subscription resumed', type: 'success' })
                        await refresh()
                      } catch (err) {
                        toast({
                          title: 'Resume failed',
                          description: err instanceof ApiError ? err.message : 'Error',
                          type: 'error',
                        })
                      }
                    }}
                  >
                    Resume Subscription
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!configured || sub?.plan === 'free'}
                    onClick={async () => {
                      try {
                        await cancelSubscription(true)
                        toast({ title: 'Cancellation scheduled', type: 'success' })
                        await refresh()
                      } catch (err) {
                        toast({
                          title: 'Cancel failed',
                          description: err instanceof ApiError ? err.message : 'Error',
                          type: 'error',
                        })
                      }
                    }}
                  >
                    Cancel Subscription
                  </Button>
                )}
              </>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Usage this period</CardTitle>
          <CardDescription>Real counters for the current billing period.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading || !usage ? (
            <p className="text-sm text-muted-foreground">Loading usage…</p>
          ) : (
            usage.items.map((item) => {
              const label = item.resource.replace(/_/g, ' ')
              const limitLabel = item.unlimited ? 'Custom' : String(item.limit ?? '—')
              return (
                <div key={item.resource} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="capitalize">{label}</span>
                    <span>
                      {item.used} / {limitLabel}
                      {item.percent != null ? ` · ${item.percent}%` : ''}
                    </span>
                  </div>
                  <Progress value={item.percent ?? (item.unlimited ? 0 : 0)} />
                </div>
              )
            })
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function TeamSettingsPanel() {
  const { toast } = useToast()
  const { hasPermission } = useAuth()
  const [members, setMembers] = useState<
    { id: string; email: string; first_name: string; last_name: string; role: string; status: string; joined_at: string | null }[]
  >([])
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('member')
  const [loading, setLoading] = useState(true)
  const canManage = hasPermission('team.manage')

  const refresh = async () => {
    setLoading(true)
    try {
      setMembers(await listTeam())
    } catch (err) {
      toast({
        title: 'Could not load team',
        description: err instanceof Error ? err.message : 'Error',
        type: 'error',
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Team</CardTitle>
        <CardDescription>Members of the active organization</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {canManage && (
          <div className="grid gap-3 sm:grid-cols-[1fr_140px_auto]">
            <Input placeholder="colleague@agency.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="admin">Admin</SelectItem>
                <SelectItem value="manager">Manager</SelectItem>
                <SelectItem value="member">Member</SelectItem>
                <SelectItem value="viewer">Viewer</SelectItem>
              </SelectContent>
            </Select>
            <Button
              onClick={async () => {
                try {
                  const res = await inviteTeamMember(email, role)
                  toast({
                    title: 'Invitation created',
                    description: res.message,
                    type: 'success',
                  })
                  setEmail('')
                  await refresh()
                } catch (err) {
                  toast({
                    title: 'Invite failed',
                    description: err instanceof Error ? err.message : 'Error',
                    type: 'error',
                  })
                }
              }}
            >
              Invite
            </Button>
          </div>
        )}
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {members.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-border py-2">
                <div>
                  <p className="font-medium">
                    {[m.first_name, m.last_name].filter(Boolean).join(' ') || m.email}
                  </p>
                  <p className="text-muted-foreground">{m.email}</p>
                </div>
                <div className="text-right text-xs text-muted-foreground">
                  <p>
                    {m.role} · {m.status}
                  </p>
                  <p>{m.joined_at ? new Date(m.joined_at).toLocaleDateString() : '—'}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function statusTone(status: string): string {
  const s = status.toLowerCase()
  if (s === 'healthy' || s === 'ok' || s === 'alive' || s === 'ready') return 'text-emerald-700 bg-emerald-50 border-emerald-200'
  if (s === 'test_mode' || s === 'degraded') return 'text-amber-800 bg-amber-50 border-amber-200'
  if (s === 'not_configured' || s === 'disabled' || s === 'not_implemented') return 'text-slate-700 bg-slate-50 border-slate-200'
  return 'text-rose-800 bg-rose-50 border-rose-200'
}

function labelFor(status: string, mode?: string): string {
  const s = (status || '').toLowerCase()
  if (s === 'healthy' && mode === 'live') return 'Live'
  if (s === 'healthy') return 'Healthy'
  if (s === 'test_mode' || mode === 'mock' || mode === 'test') return mode === 'mock' ? 'Mock' : 'Test Mode'
  if (s === 'not_configured' || mode === 'unavailable') return 'Not Configured'
  if (s === 'degraded') return 'Degraded'
  if (s === 'disabled') return 'Disabled'
  if (s === 'unavailable') return 'Unavailable'
  if (s === 'not_implemented') return 'Not Implemented'
  return status
}

function modeBadge(mode?: string): string {
  const m = (mode || '').toLowerCase()
  if (m === 'live') return 'LIVE PROVIDER'
  if (m === 'test') return 'TEST MODE'
  if (m === 'mock') return 'MOCK'
  if (m === 'disabled') return 'DISABLED'
  if (m === 'error') return 'DEGRADED'
  return 'NOT CONFIGURED'
}

function SystemHealthPanel() {
  const { toast } = useToast()
  const { hasPermission } = useAuth()
  const canManage = hasPermission('integrations.manage')
  const [data, setData] = useState<SystemHealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [testing, setTesting] = useState<string | null>(null)
  const [tab, setTab] = useState('overview')
  const [logs, setLogs] = useState<Record<string, unknown>[]>([])
  const [jobs, setJobs] = useState<Record<string, unknown>[]>([])
  const [audit, setAudit] = useState<Record<string, unknown>[]>([])
  const [config, setConfig] = useState<ConfigValidateResponse | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const health = await getSystemHealth()
      setData(health)
      if (canManage) {
        const [l, j, a, c] = await Promise.all([
          getProviderLogs().catch(() => ({ items: [] })),
          getSystemJobs().catch(() => ({ items: [] })),
          getSystemAudit().catch(() => ({ items: [] })),
          validateConfig().catch(() => null),
        ])
        setLogs(l.items || [])
        setJobs(j.items || [])
        setAudit(a.items || [])
        setConfig(c)
      }
    } catch (err) {
      setData(null)
      setError(err instanceof ApiError ? err.message : 'Backend unavailable')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canManage])

  const providerKeys: [string, string][] = [
    ['google_places', 'Google Places'],
    ['ai', 'AI'],
    ['email_verification', 'Email Verification'],
    ['email_sending', 'Email Sending'],
    ['email_inbound', 'Inbound Email'],
    ['calendar', 'Calendar'],
    ['billing', 'Billing'],
  ]

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>System Health</CardTitle>
            <CardDescription>
              Provider modes never claim LIVE from API keys alone.
              {data ? ` · env=${data.app_env}` : null}
            </CardDescription>
          </div>
          <Button variant="outline" onClick={() => void refresh()} disabled={loading}>
            Refresh
          </Button>
        </CardHeader>
        <CardContent>
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="mb-4">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="providers">Providers</TabsTrigger>
              <TabsTrigger value="jobs">Jobs</TabsTrigger>
              <TabsTrigger value="audit">Audit</TabsTrigger>
              <TabsTrigger value="configuration">Configuration</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-3">
              {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
              {error && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
                  {error}
                </div>
              )}
              {data && (
                <>
                  <div className="rounded-xl border border-border p-4 text-sm">
                    <p>
                      Database: <strong>{data.database.status}</strong>
                    </p>
                    <p>
                      Auth: <strong>{data.authentication.status}</strong>
                    </p>
                    <p>
                      Jobs: <strong>{data.job_queue.backend}</strong> ({data.job_queue.status})
                    </p>
                    <p>Config OK: {data.config_ok ? 'yes' : 'no'}</p>
                  </div>
                </>
              )}
            </TabsContent>

            <TabsContent value="providers" className="space-y-3">
              {data &&
                providerKeys.map(([key, title]) => {
                  const p = data.providers?.[key] || data.providers?.[key === 'email_inbound' ? 'reply_inbound' : key]
                  if (!p) return null
                  return (
                    <div
                      key={key}
                      className="flex flex-col gap-2 rounded-xl border border-border p-4 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div>
                        <p className="font-medium">{title}</p>
                        <p className="text-xs text-muted-foreground">
                          {modeBadge(String(p.mode))}
                          {p.last_checked ? ` · checked ${new Date(String(p.last_checked)).toLocaleString()}` : ''}
                        </p>
                        {p.last_error ? (
                          <p className="text-xs text-rose-700 mt-1">{String(p.last_error)}</p>
                        ) : null}
                        {p.last_success ? (
                          <p className="text-xs text-muted-foreground">
                            Last success: {new Date(String(p.last_success)).toLocaleString()}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={cn('rounded-md border px-2 py-1 text-xs font-medium', statusTone(String(p.status)))}>
                          {labelFor(String(p.status), String(p.mode))}
                        </span>
                        {canManage && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={testing === key}
                            onClick={async () => {
                              setTesting(key)
                              try {
                                const res = await testProvider(key)
                                toast({
                                  title: res.ok ? 'Provider test ok' : 'Provider test failed',
                                  description: res.message,
                                  type: res.ok ? 'success' : 'error',
                                })
                                await refresh()
                              } catch (err) {
                                toast({
                                  title: 'Test failed',
                                  description: err instanceof ApiError ? err.message : 'Unknown error',
                                  type: 'error',
                                })
                              } finally {
                                setTesting(null)
                              }
                            }}
                          >
                            Test
                          </Button>
                        )}
                      </div>
                    </div>
                  )
                })}
              {!canManage && (
                <p className="text-sm text-muted-foreground">Only owners/admins can run provider tests.</p>
              )}
            </TabsContent>

            <TabsContent value="jobs" className="space-y-2 text-sm">
              {jobs.length === 0 ? (
                <p className="text-muted-foreground">No recent jobs (or insufficient permission).</p>
              ) : (
                jobs.map((j) => (
                  <div key={String(j.id)} className="rounded-lg border border-border px-3 py-2">
                    {String(j.job_type)} · {String(j.status)}
                    {j.last_error ? ` · ${String(j.last_error)}` : ''}
                  </div>
                ))
              )}
            </TabsContent>

            <TabsContent value="audit" className="space-y-2 text-sm">
              {audit.length === 0 ? (
                <p className="text-muted-foreground">No recent audit events.</p>
              ) : (
                audit.slice(0, 20).map((a) => (
                  <div key={String(a.id)} className="rounded-lg border border-border px-3 py-2">
                    {String(a.action)} · {a.created_at ? new Date(String(a.created_at)).toLocaleString() : ''}
                  </div>
                ))
              )}
              {logs.length > 0 && (
                <div className="pt-4">
                  <p className="font-medium mb-2">Provider operation logs</p>
                  {logs.slice(0, 10).map((l) => (
                    <div key={String(l.id)} className="rounded-lg border border-border px-3 py-2 mb-1">
                      {String(l.provider)} · {String(l.status)} · {String(l.operation)}
                    </div>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="configuration" className="space-y-2 text-sm">
              {!config ? (
                <p className="text-muted-foreground">Configuration validation requires admin permission.</p>
              ) : (
                <>
                  <p>
                    Errors: {config.error_count} · Warnings: {config.warning_count}
                  </p>
                  {config.items.map((item) => (
                    <div key={item.code} className="rounded-lg border border-border px-3 py-2">
                      <span className="font-medium">{item.severity.toUpperCase()}</span> · {item.code}: {item.message}
                    </div>
                  ))}
                </>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}

function ProductionReadinessPanel() {
  const { toast } = useToast()
  const { hasPermission } = useAuth()
  const canManage = hasPermission('integrations.manage')
  const [data, setData] = useState<ReadinessResponse | null>(null)
  const [matrix, setMatrix] = useState<ProviderMatrixRow[] | null>(null)
  const [matrixNote, setMatrixNote] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!canManage) {
      setLoading(false)
      return
    }
    void (async () => {
      try {
        const [readiness, matrixRes] = await Promise.all([getReadiness(), getProviderMatrix()])
        setData(readiness)
        setMatrix(matrixRes.providers)
        setMatrixNote(matrixRes.note || null)
      } catch (err) {
        toast({
          title: 'Failed to load readiness',
          description: err instanceof ApiError ? err.message : 'Error',
          type: 'error',
        })
      } finally {
        setLoading(false)
      }
    })()
  }, [canManage, toast])

  if (!canManage) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Production Readiness</CardTitle>
          <CardDescription>Owner/admin only.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const tone = (s: string) => {
    if (s === 'PASS') return 'text-emerald-700 bg-emerald-50 border-emerald-200'
    if (s === 'WARNING') return 'text-amber-800 bg-amber-50 border-amber-200'
    return 'text-rose-800 bg-rose-50 border-rose-200'
  }

  const resultTone = (s: string) => {
    if (s === 'PASS' || s === 'TEST') return 'text-emerald-700 bg-emerald-50 border-emerald-200'
    if (s === 'CONFIGURED' || s === 'DISABLED') return 'text-amber-800 bg-amber-50 border-amber-200'
    if (s === 'MOCK') return 'text-slate-700 bg-slate-50 border-slate-200'
    return 'text-rose-800 bg-rose-50 border-rose-200'
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Production Readiness</CardTitle>
          <CardDescription>
            PASS only when verified. API keys alone never imply LIVE.
            {data ? ` · blocked=${data.blocked_count} warnings=${data.warning_count}` : null}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading && <p className="text-sm text-muted-foreground">Loading checklist…</p>}
          {data?.checklist.map((item) => (
            <div
              key={item.id}
              className="flex flex-col gap-1 rounded-xl border border-border p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <p className="font-medium">{item.label || item.id}</p>
                <p className="text-sm text-muted-foreground">{item.detail}</p>
              </div>
              <span className={cn('rounded-md border px-2 py-1 text-xs font-medium w-fit', tone(item.status))}>
                {item.status}
              </span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Provider matrix</CardTitle>
          <CardDescription>
            {matrixNote || 'Configured ≠ Live-tested ≠ LIVE. Never invent LIVE.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {matrix?.map((row) => (
            <div
              key={row.provider}
              className="flex flex-col gap-1 rounded-xl border border-border p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <p className="font-medium">{row.provider}</p>
                <p className="text-sm text-muted-foreground">
                  configured={row.configured ? 'YES' : 'NO'} · mode={row.mode} · live_tested=
                  {row.live_tested ? 'YES' : 'NO'}
                  {row.last_checked ? ` · last_checked=${row.last_checked}` : ''}
                </p>
              </div>
              <span className={cn('rounded-md border px-2 py-1 text-xs font-medium w-fit', resultTone(row.result))}>
                {row.result}
              </span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

function MeetingsSettingsPanel() {
  const { toast } = useToast()
  const [types, setTypes] = useState<MeetingType[]>([])
  const [rules, setRules] = useState<AvailabilityRule[]>([])
  const [calendarNote, setCalendarNote] = useState('Calendar provider: Not configured')
  const [typeName, setTypeName] = useState('AI Automation Consultation')
  const [duration, setDuration] = useState(30)

  async function refresh() {
    try {
      const [t, r, c] = await Promise.all([
        listMeetingTypes(),
        listAvailability(),
        getCalendarStatus().catch(() => null),
      ])
      setTypes(t)
      setRules(r)
      if (c) {
        setCalendarNote(
          c.calendar_live
            ? `Calendar: ${c.provider} (live)`
            : `Calendar provider: ${c.configured ? `${c.provider} (not live)` : 'Not configured'}`,
        )
      }
    } catch (err) {
      toast({
        title: 'Failed to load meeting settings',
        description: err instanceof ApiError ? err.message : 'Unknown error',
        type: 'error',
      })
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Calendar integration</CardTitle>
          <CardDescription>{calendarNote}</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Google Calendar / Outlook are not connected. Mock calendar may be used in tests only.
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Meeting types</CardTitle>
          <CardDescription>Duration and buffers used for slot generation.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Name">
              <Input value={typeName} onChange={(e) => setTypeName(e.target.value)} />
            </Field>
            <Field label="Duration (minutes)">
              <Input
                type="number"
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
              />
            </Field>
            <div className="flex items-end">
              <Button
                onClick={async () => {
                  try {
                    await createMeetingType({
                      name: typeName,
                      duration_minutes: duration,
                      buffer_before_minutes: 0,
                      buffer_after_minutes: 0,
                      active: true,
                    })
                    toast({ title: 'Meeting type created', type: 'success' })
                    await refresh()
                  } catch (err) {
                    toast({
                      title: 'Create failed',
                      description: err instanceof ApiError ? err.message : 'Unknown error',
                      type: 'error',
                    })
                  }
                }}
              >
                Add type
              </Button>
            </div>
          </div>
          <ul className="space-y-1 text-sm">
            {types.map((t) => (
              <li key={t.id}>
                {t.name} · {t.duration_minutes}m {t.active ? '' : '(inactive)'}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Availability</CardTitle>
          <CardDescription>Weekly rules (Mon=0 … Sun=6). Not hardcoded.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button
            variant="outline"
            onClick={async () => {
              try {
                for (let d = 0; d <= 4; d++) {
                  await createAvailability({
                    day_of_week: d,
                    start_time: '09:00:00',
                    end_time: '17:00:00',
                    timezone: 'UTC',
                  })
                }
                toast({ title: 'Weekday 09:00–17:00 UTC added', type: 'success' })
                await refresh()
              } catch (err) {
                toast({
                  title: 'Availability failed',
                  description: err instanceof ApiError ? err.message : 'Unknown error',
                  type: 'error',
                })
              }
            }}
          >
            Add Mon–Fri 09:00–17:00 UTC
          </Button>
          <ul className="space-y-1 text-sm">
            {rules.map((r) => (
              <li key={r.id}>
                Day {r.day_of_week}: {String(r.start_time).slice(0, 5)}–{String(r.end_time).slice(0, 5)} (
                {r.timezone})
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      {children}
    </div>
  )
}

function ToggleRow({
  label,
  description,
  checked,
  onCheckedChange,
}: {
  label: string
  description: string
  checked: boolean
  onCheckedChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-xl border border-border p-4">
      <div>
        <p className="font-medium">{label}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  )
}
