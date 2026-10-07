import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CalendarRange, Flame, MailCheck, RefreshCw, Users, Video } from 'lucide-react'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { ChartCard } from '@/components/shared/ChartCard'
import { SkeletonDashboard } from '@/components/shared/Skeleton'
import { LeadScore } from '@/components/shared/LeadScore'
import { EmailStatusBadge, OpportunityBadge, OutreachStatusBadge } from '@/components/shared/StatusBadge'
import { LeadCard } from '@/components/shared/LeadTable'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { useSimulatedLoading } from '@/hooks/useMediaQuery'
import {
  dashboardStats,
  leadGenerationSeries,
  leadSourcesChart,
  leads,
  opportunityDistribution,
  outreachPerformance,
} from '@/data/mock'
import { getQualificationStats, type QualificationStats } from '@/api/qualification'
import { getSendingStats, type SendingStats } from '@/api/sending'
import { getReplyStats, type ReplyStats } from '@/api/replies'
import { chartTooltipStyle, formatNumber, getGreeting, initials } from '@/lib/utils'
import { softTransition } from '@/lib/motion'

export function DashboardPage() {
  const { loading, refresh } = useSimulatedLoading(900)
  const [range, setRange] = useState('30d')
  const [aiStats, setAiStats] = useState<QualificationStats | null>(null)
  const [sendStats, setSendStats] = useState<SendingStats | null>(null)
  const [replyStats, setReplyStats] = useState<ReplyStats | null>(null)
  const recent = leads.slice(0, 6)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      getQualificationStats().catch(() => null),
      getSendingStats().catch(() => null),
      getReplyStats().catch(() => null),
    ]).then(([ai, send, replies]) => {
      if (cancelled) return
      setAiStats(ai)
      setSendStats(send)
      setReplyStats(replies)
    })
    return () => {
      cancelled = true
    }
  }, [loading])

  if (loading) {
    return (
      <div>
        <PageHeader title={`${getGreeting()}, Roshan`} description="Loading your lead intelligence..." />
        <SkeletonDashboard />
      </div>
    )
  }

  const useRealAi = Boolean(aiStats?.has_real_data)
  const useRealSend = Boolean(sendStats?.has_real_data)
  const useRealReplies = Boolean(replyStats?.has_real_data)
  const hotValue = useRealAi ? aiStats!.hot_leads : dashboardStats.hotLeads

  return (
    <div className="min-w-0">
      <PageHeader
        title={`${getGreeting()}, Roshan`}
        description="Find high-quality businesses that are ready for your services."
        actions={
          <>
            <Select value={range} onValueChange={setRange}>
              <SelectTrigger className="w-full min-w-0 sm:w-[150px]" aria-label="Date range">
                <CalendarRange className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7d">Last 7 days</SelectItem>
                <SelectItem value="30d">Last 30 days</SelectItem>
                <SelectItem value="90d">Last 90 days</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={refresh} aria-label="Refresh dashboard">
              <RefreshCw className="h-4 w-4" />
              <span className="hidden xs:inline sm:inline">Refresh</span>
            </Button>
          </>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-4">
        <StatCard
          title={useRealAi ? 'Qualified Leads' : 'Total Leads'}
          value={useRealAi ? aiStats!.total_qualified : dashboardStats.totalLeads}
          change={useRealAi ? undefined : dashboardStats.totalLeadsChange}
          icon={Users}
          delay={0}
        />
        <StatCard
          title="Hot Leads"
          value={hotValue}
          change={useRealAi ? undefined : dashboardStats.hotLeadsChange}
          icon={Flame}
          delay={0.05}
        />
        <StatCard
          title={useRealSend ? 'Emails Sent' : 'Emails Verified'}
          value={useRealSend ? sendStats!.emails_sent : dashboardStats.emailsVerified}
          change={useRealSend ? undefined : dashboardStats.emailsVerifiedChange}
          icon={MailCheck}
          delay={0.1}
        />
        <StatCard
          title={
            useRealReplies
              ? 'Replies'
              : useRealSend
                ? sendStats!.delivery_data_available
                  ? 'Delivered'
                  : 'Delivery unavailable'
                : useRealAi
                  ? 'Avg AI Score'
                  : 'Meetings'
          }
          value={
            useRealReplies
              ? replyStats!.total_replies
              : useRealSend
                ? sendStats!.delivery_data_available
                  ? sendStats!.delivered
                  : 0
                : useRealAi
                  ? Math.round(aiStats!.average_score ?? 0)
                  : dashboardStats.meetings
          }
          change={useRealReplies || useRealSend || useRealAi ? undefined : dashboardStats.meetingsChange}
          icon={useRealReplies ? MailCheck : Video}
          delay={0.15}
        />
      </div>

      <p className="mt-3 text-sm text-muted-foreground">
        {useRealReplies ? (
          <>
            Real replies:{' '}
            <span className="font-medium text-foreground">{formatNumber(replyStats!.total_replies)}</span>
            {' · '}
            <span className="font-medium text-foreground">
              {formatNumber(replyStats!.interested)} interested
            </span>
            {' · '}
            <span className="font-medium text-foreground">
              {formatNumber(replyStats!.meeting_requests)} meeting requests
            </span>
            {replyStats!.reply_rate != null ? (
              <>
                {' · '}
                reply rate{' '}
                <span className="font-medium text-foreground">
                  {(replyStats!.reply_rate * 100).toFixed(1)}%
                </span>
              </>
            ) : null}
            . Not live-tested unless a provider webhook delivered the event.
          </>
        ) : useRealSend ? (
          <>
            Real sending:{' '}
            <span className="font-medium text-foreground">{formatNumber(sendStats!.emails_sent)} sent</span>
            {' · '}
            <span className="font-medium text-foreground">{formatNumber(sendStats!.bounced)} bounced</span>
            {' · '}
            <span className="font-medium text-foreground">{formatNumber(sendStats!.failed)} failed</span>
            {' · '}
            <span className="font-medium text-foreground">{formatNumber(sendStats!.suppressed)} suppressed</span>
            {sendStats!.delivery_data_available ? (
              <>
                {' · '}
                Delivery rate:{' '}
                <span className="font-medium text-foreground">
                  {Math.round((sendStats!.delivery_rate ?? 0) * 100)}%
                </span>
              </>
            ) : (
              <> · Delivery data unavailable</>
            )}
          </>
        ) : useRealAi ? (
          <>
            Real AI qualification:{' '}
            <span className="font-medium text-foreground">{formatNumber(aiStats!.hot_leads)} hot</span>
            {' · '}
            <span className="font-medium text-foreground">{formatNumber(aiStats!.warm_leads)} warm</span>
            {aiStats!.top_opportunity ? (
              <>
                {' · '}
                Top opportunity:{' '}
                <span className="font-medium capitalize text-foreground">
                  {aiStats!.top_opportunity.replaceAll('_', ' ')}
                </span>
              </>
            ) : null}
          </>
        ) : (
          <>
            Pipeline snapshot (demo until real qualification/sending data exists):{' '}
            <span className="font-medium text-foreground">{formatNumber(dashboardStats.hotLeads)} hot leads</span>
            {' · '}
            <span className="font-medium text-foreground">{formatNumber(dashboardStats.emailsVerified)} verified emails</span>
            {' · '}
            <span className="font-medium text-foreground">{formatNumber(dashboardStats.meetings)} meetings booked</span>
          </>
        )}
      </p>

      <div className="mt-5 grid min-w-0 gap-4 lg:mt-6 lg:grid-cols-2">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ ...softTransition, delay: 0.1 }}>
          <ChartCard title="Lead Generation Overview" description="Leads generated, qualified, and hot over time">
            <div className="chart-wrap h-56 sm:h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={leadGenerationSeries} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="leadsFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} tick={{ fill: 'var(--color-muted-foreground)' }} />
                  <YAxis tickLine={false} axisLine={false} fontSize={12} width={36} tick={{ fill: 'var(--color-muted-foreground)' }} />
                  <Tooltip contentStyle={chartTooltipStyle} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="leads" name="Leads" stroke="var(--color-chart-1)" fill="url(#leadsFill)" strokeWidth={2} />
                  <Area type="monotone" dataKey="qualified" name="Qualified" stroke="var(--color-chart-2)" fill="transparent" strokeWidth={2} />
                  <Area type="monotone" dataKey="hot" name="Hot" stroke="var(--color-chart-4)" fill="transparent" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ ...softTransition, delay: 0.15 }}>
          <ChartCard title="Lead Sources" description="Where your best leads come from">
            <div className="flex h-56 flex-col items-center justify-center gap-4 sm:h-64 sm:flex-row">
              <div className="h-40 w-40 shrink-0 sm:h-48 sm:w-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={leadSourcesChart} dataKey="value" nameKey="name" innerRadius={42} outerRadius={68} paddingAngle={3}>
                      {leadSourcesChart.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={chartTooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="w-full max-w-[220px] space-y-2">
                {leadSourcesChart.map((s) => (
                  <div key={s.name} className="flex items-center gap-2 text-sm">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: s.color }} />
                    <span className="min-w-0 flex-1 truncate text-muted-foreground">{s.name}</span>
                    <span className="font-medium tabular-nums">{s.value}%</span>
                  </div>
                ))}
              </div>
            </div>
          </ChartCard>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ ...softTransition, delay: 0.2 }}>
          <ChartCard title="Opportunity Distribution" description="Service opportunities across your pipeline">
            <div className="chart-wrap h-56 sm:h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={opportunityDistribution} layout="vertical" margin={{ left: 4, right: 12, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
                  <XAxis type="number" hide />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={100}
                    tickLine={false}
                    axisLine={false}
                    fontSize={11}
                    tick={{ fill: 'var(--color-muted-foreground)' }}
                  />
                  <Tooltip contentStyle={chartTooltipStyle} />
                  <Bar dataKey="value" name="Leads" fill="var(--color-chart-1)" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ ...softTransition, delay: 0.25 }}>
          <ChartCard title="Outreach Performance" description="Sent, delivered, replies, and meetings">
            <div className="chart-wrap h-48 sm:h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={outreachPerformance} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={12} tick={{ fill: 'var(--color-muted-foreground)' }} />
                  <YAxis tickLine={false} axisLine={false} fontSize={12} width={40} tick={{ fill: 'var(--color-muted-foreground)' }} />
                  <Tooltip contentStyle={chartTooltipStyle} />
                  <Bar dataKey="value" name="Count" fill="var(--color-chart-2)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {outreachPerformance.map((item) => (
                <div key={item.name} className="rounded-lg bg-muted/50 px-3 py-2">
                  <p className="text-xs text-muted-foreground">{item.name}</p>
                  <p className="font-semibold tabular-nums">{formatNumber(item.value)}</p>
                </div>
              ))}
            </div>
          </ChartCard>
        </motion.div>
      </div>

      <motion.div
        className="mt-5 lg:mt-6"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...softTransition, delay: 0.3 }}
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Recent Leads</h2>
          <Link
            to="/leads"
            className="inline-flex h-8 items-center justify-center rounded-md border border-border bg-card px-3 text-xs font-medium transition-colors hover:bg-muted"
          >
            View All Leads
          </Link>
        </div>

        {/* Mobile cards */}
        <div className="grid gap-3 md:hidden">
          {recent.map((lead) => (
            <LeadCard key={lead.id} lead={lead} selected={false} onSelect={() => undefined} />
          ))}
        </div>

        {/* Desktop table */}
        <div className="hidden overflow-hidden rounded-xl border border-border bg-card md:block">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] text-left text-sm">
              <thead className="border-b border-border bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Company</th>
                  <th className="px-4 py-3 font-medium">Industry</th>
                  <th className="px-4 py-3 font-medium">Location</th>
                  <th className="px-4 py-3 font-medium">Website</th>
                  <th className="px-4 py-3 font-medium">Opportunity</th>
                  <th className="px-4 py-3 font-medium">Lead Score</th>
                  <th className="px-4 py-3 font-medium">Email</th>
                  <th className="px-4 py-3 font-medium">Outreach</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {recent.map((lead) => (
                  <tr key={lead.id} className="transition-colors hover:bg-muted/40">
                    <td className="px-4 py-3">
                      <Link to={`/leads/${lead.id}`} className="flex items-center gap-3">
                        <Avatar className="h-8 w-8">
                          <AvatarFallback className="bg-primary/10 text-[10px] text-primary">
                            {initials(lead.company)}
                          </AvatarFallback>
                        </Avatar>
                        <span className="font-medium">{lead.company}</span>
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{lead.industry}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {lead.city}, {lead.country}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{lead.website ?? '—'}</td>
                    <td className="px-4 py-3">
                      <OpportunityBadge opportunity={lead.opportunity} />
                    </td>
                    <td className="px-4 py-3">
                      <LeadScore score={lead.score} size="sm" />
                    </td>
                    <td className="px-4 py-3">
                      <EmailStatusBadge status={lead.emailStatus} />
                    </td>
                    <td className="px-4 py-3">
                      <OutreachStatusBadge status={lead.outreachStatus} />
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {new Date(lead.createdAt).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
