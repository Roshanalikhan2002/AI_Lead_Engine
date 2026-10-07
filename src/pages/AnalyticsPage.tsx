import { useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Funnel,
  FunnelChart,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { PageHeader } from '@/components/shared/PageHeader'
import { ChartCard } from '@/components/shared/ChartCard'
import { StatCard } from '@/components/shared/StatCard'
import { SkeletonDashboard } from '@/components/shared/Skeleton'
import { Button } from '@/components/ui/button'
import { useSimulatedLoading } from '@/hooks/useMediaQuery'
import {
  analyticsByCountry,
  analyticsByIndustry,
  analyticsLeadsOverTime,
  conversionFunnel,
  opportunityDistribution,
} from '@/data/mock'
import {
  Flame,
  LineChart as LineChartIcon,
  Mail,
  MessageSquare,
  Percent,
  Target,
  Video,
} from 'lucide-react'
import { chartTooltipStyle, cn } from '@/lib/utils'

const ranges = [
  { id: '7d', label: '7 days' },
  { id: '30d', label: '30 days' },
  { id: '90d', label: '90 days' },
  { id: 'custom', label: 'Custom' },
]

export function AnalyticsPage() {
  const { loading } = useSimulatedLoading(900)
  const [range, setRange] = useState('30d')

  if (loading) {
    return (
      <div>
        <PageHeader title="Analytics" description="Loading insights..." />
        <SkeletonDashboard />
      </div>
    )
  }

  return (
    <div className="min-w-0">
      <PageHeader
        title="Analytics"
        description="Deep insights across generation, qualification, and conversion."
        breadcrumbs={[{ label: 'Analytics' }]}
        actions={
          <div className="flex w-full flex-wrap gap-1 rounded-lg bg-muted p-1 sm:w-auto" role="group" aria-label="Date range">
            {ranges.map((r) => (
              <Button
                key={r.id}
                size="sm"
                variant={range === r.id ? 'secondary' : 'ghost'}
                className={cn('flex-1 sm:flex-none', range === r.id && 'shadow-sm')}
                onClick={() => setRange(r.id)}
              >
                {r.label}
              </Button>
            ))}
          </div>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-4">
        <StatCard title="Lead Generation" value={12540} change={18.4} icon={LineChartIcon} delay={0} />
        <StatCard title="Lead Qualification" value={6820} change={14.2} icon={Target} delay={0.04} />
        <StatCard title="Website Opportunities" value={4120} change={11.6} icon={Flame} delay={0.08} />
        <StatCard title="Email Performance" value={4280} change={9.8} icon={Mail} delay={0.12} />
        <StatCard title="Reply Rate" value={14} change={2.4} icon={MessageSquare} delay={0.16} />
        <StatCard title="Meeting Rate" value={2} change={1.1} icon={Video} delay={0.2} />
        <StatCard title="Conversion Rate" value={0.6} change={0.3} icon={Percent} delay={0.24} />
        <StatCard title="Hot Leads" value={1248} change={12.8} icon={Flame} delay={0.28} />
      </div>

      <div className="mt-5 grid min-w-0 gap-4 lg:mt-6 lg:grid-cols-2">
        <ChartCard title="Leads over time" description="Discovered vs qualified">
          <div className="chart-wrap h-56 sm:h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analyticsLeadsOverTime} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="analyticsFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tickLine={false} axisLine={false} fontSize={12} tick={{ fill: 'var(--color-muted-foreground)' }} />
                <YAxis tickLine={false} axisLine={false} fontSize={12} width={36} tick={{ fill: 'var(--color-muted-foreground)' }} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Area type="monotone" dataKey="leads" name="Leads" stroke="var(--color-chart-1)" fill="url(#analyticsFill)" strokeWidth={2} />
                <Area type="monotone" dataKey="qualified" name="Qualified" stroke="var(--color-chart-2)" fill="transparent" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Leads by country">
          <div className="chart-wrap h-56 sm:h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analyticsByCountry} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="country" tickLine={false} axisLine={false} fontSize={12} tick={{ fill: 'var(--color-muted-foreground)' }} />
                <YAxis tickLine={false} axisLine={false} fontSize={12} width={40} tick={{ fill: 'var(--color-muted-foreground)' }} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Bar dataKey="leads" fill="var(--color-chart-1)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Leads by industry">
          <div className="chart-wrap h-56 sm:h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={analyticsByIndustry} layout="vertical" margin={{ left: 4, right: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="industry"
                  width={80}
                  tickLine={false}
                  axisLine={false}
                  fontSize={11}
                  tick={{ fill: 'var(--color-muted-foreground)' }}
                />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Bar dataKey="leads" fill="var(--color-chart-2)" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Opportunities">
          <div className="chart-wrap h-56 sm:h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={opportunityDistribution} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis
                  dataKey="name"
                  tickLine={false}
                  axisLine={false}
                  fontSize={10}
                  interval={0}
                  angle={-25}
                  textAnchor="end"
                  height={60}
                  tick={{ fill: 'var(--color-muted-foreground)' }}
                />
                <YAxis tickLine={false} axisLine={false} fontSize={12} width={36} tick={{ fill: 'var(--color-muted-foreground)' }} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Bar dataKey="value" fill="var(--color-chart-3)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Conversion funnel" className="lg:col-span-2">
          <div className="chart-wrap h-64 sm:h-72">
            <ResponsiveContainer width="100%" height="100%">
              <FunnelChart>
                <Tooltip contentStyle={chartTooltipStyle} />
                <Funnel dataKey="value" data={conversionFunnel} isAnimationActive fill="var(--color-primary)">
                  <LabelList position="right" fill="var(--color-foreground)" stroke="none" dataKey="stage" />
                </Funnel>
              </FunnelChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </div>
    </div>
  )
}
