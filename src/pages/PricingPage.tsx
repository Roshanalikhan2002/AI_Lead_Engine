import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { listBillingPlans, type PlanInfo } from '@/api/billing'
import { ApiError } from '@/api/client'
import { useToast } from '@/components/shared/Toast'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

const FEATURE_ROWS: { key: string; label: string }[] = [
  { key: 'leads_discovered', label: 'Lead discovery' },
  { key: 'website_analyses', label: 'Website intelligence' },
  { key: 'emails_discovered', label: 'Email discovery' },
  { key: 'emails_verified', label: 'Email verification' },
  { key: 'ai_qualifications', label: 'AI qualification' },
  { key: 'ai_generations', label: 'AI outreach' },
  { key: 'active_campaigns', label: 'Campaigns' },
  { key: 'ai_reply_classifications', label: 'Reply intelligence' },
  { key: 'meetings_booked', label: 'Meetings' },
  { key: 'team_members', label: 'Team members' },
]

function formatLimit(v: number | null | undefined): string {
  if (v == null) return 'Custom'
  return String(v)
}

function formatPrice(plan: PlanInfo, interval: 'month' | 'year'): string {
  if (plan.contact_sales || plan.monthly_price == null) return 'Contact Sales'
  const amount = interval === 'year' ? plan.annual_price : plan.monthly_price
  if (amount == null) return 'Contact Sales'
  return `${plan.currency} ${amount.toFixed(0)}/${interval === 'year' ? 'yr' : 'mo'}`
}

export function PricingPage() {
  const { toast } = useToast()
  const { organization, hasPermission } = useAuth()
  const [plans, setPlans] = useState<PlanInfo[]>([])
  const [interval, setInterval] = useState<'month' | 'year'>('month')
  const [loading, setLoading] = useState(true)
  const canManage = hasPermission?.('billing.manage') ?? false

  useEffect(() => {
    void (async () => {
      try {
        const res = await listBillingPlans()
        setPlans(res.plans)
      } catch (err) {
        toast({
          title: 'Failed to load plans',
          description: err instanceof ApiError ? err.message : 'Unknown error',
          type: 'error',
        })
      } finally {
        setLoading(false)
      }
    })()
  }, [toast])

  const current = (organization?.plan || 'free').toLowerCase()

  return (
    <div className="min-w-0">
      <PageHeader
        title="Pricing"
        description="Compare plans. Limits come from your workspace configuration — not marketing claims."
        breadcrumbs={[{ label: 'Management' }, { label: 'Pricing' }]}
      />

      <div className="mb-6 flex items-center gap-2">
        <Button
          size="sm"
          variant={interval === 'month' ? 'default' : 'outline'}
          onClick={() => setInterval('month')}
        >
          Monthly
        </Button>
        <Button
          size="sm"
          variant={interval === 'year' ? 'default' : 'outline'}
          onClick={() => setInterval('year')}
        >
          Annual
        </Button>
        <Button asChild size="sm" variant="ghost">
          <Link to="/settings?tab=billing">Usage & Billing</Link>
        </Button>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading plans…</p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-5 md:grid-cols-2">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className={cn(
                'rounded-xl border border-border p-4 flex flex-col gap-3',
                plan.id === current && 'ring-2 ring-primary',
              )}
            >
              <div>
                <h3 className="text-lg font-semibold">{plan.name}</h3>
                <p className="text-sm text-muted-foreground mt-1">{plan.description}</p>
              </div>
              <p className="text-2xl font-semibold tracking-tight">{formatPrice(plan, interval)}</p>
              <ul className="space-y-1 text-sm flex-1">
                {FEATURE_ROWS.slice(0, 6).map((row) => (
                  <li key={row.key} className="flex justify-between gap-2">
                    <span className="text-muted-foreground">{row.label}</span>
                    <span>{formatLimit(plan.limits[row.key])}</span>
                  </li>
                ))}
              </ul>
              {plan.id === current ? (
                <Button disabled variant="secondary">
                  Current plan
                </Button>
              ) : plan.contact_sales ? (
                <Button variant="outline" disabled>
                  Contact Sales
                </Button>
              ) : canManage ? (
                <Button asChild>
                  <Link to={`/settings?tab=billing&upgrade=${plan.id}`}>Choose {plan.name}</Link>
                </Button>
              ) : (
                <Button variant="outline" disabled>
                  Ask an admin to upgrade
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="mt-10 overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-border text-left">
              <th className="py-2 pr-4 font-medium">Feature / limit</th>
              {plans.map((p) => (
                <th key={p.id} className="py-2 px-2 font-medium">
                  {p.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FEATURE_ROWS.map((row) => (
              <tr key={row.key} className="border-b border-border/60">
                <td className="py-2 pr-4 text-muted-foreground">{row.label}</td>
                {plans.map((p) => (
                  <td key={p.id} className="py-2 px-2">
                    {formatLimit(p.limits[row.key])}
                  </td>
                ))}
              </tr>
            ))}
            <tr className="border-b border-border/60">
              <td className="py-2 pr-4 text-muted-foreground">Reply intelligence</td>
              {plans.map((p) => (
                <td key={p.id} className="py-2 px-2">
                  {p.features.includes('reply_intelligence') ? 'Yes' : '—'}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-2 pr-4 text-muted-foreground">Advanced analytics</td>
              {plans.map((p) => (
                <td key={p.id} className="py-2 px-2">
                  {p.features.includes('advanced_analytics') ? 'Yes' : '—'}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
