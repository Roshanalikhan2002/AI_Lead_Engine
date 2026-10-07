import { ProgressRing } from '@/components/shared/LeadScore'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { WebsiteAnalysis } from '@/types'
import { cn, scoreQuality } from '@/lib/utils'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'

interface WebsiteScoreProps {
  analysis: WebsiteAnalysis
  className?: string
  analyzing?: boolean
}

function scoreMeta(value: number) {
  const quality = scoreQuality(value)
  if (quality === 'good') {
    return { stroke: 'stroke-success', label: 'Good', badge: 'success' as const }
  }
  if (quality === 'warning') {
    return { stroke: 'stroke-warning', label: 'Warning', badge: 'warning' as const }
  }
  return { stroke: 'stroke-destructive', label: 'Critical', badge: 'destructive' as const }
}

export function WebsiteScore({ analysis, className, analyzing }: WebsiteScoreProps) {
  if (analyzing || analysis.analysisStatus === 'pending' || analysis.analysisStatus === 'running') {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Website Analysis</CardTitle>
          <CardDescription>Analyzing website…</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3 rounded-xl border border-border bg-muted/30 p-6">
            <Loader2 className="h-5 w-5 animate-spin text-primary" aria-hidden />
            <div>
              <p className="font-medium">Analyzing website...</p>
              <p className="text-sm text-muted-foreground">Collecting deterministic HTML and HTTP signals.</p>
            </div>
          </div>
          <div className="mt-4 h-24 shimmer rounded-xl bg-muted/40" />
        </CardContent>
      </Card>
    )
  }

  if (!analysis.exists || analysis.analysisStatus === 'not_available') {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Website Analysis</CardTitle>
          <CardDescription>Digital presence assessment</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
            <Badge variant="destructive" className="mb-3">
              Critical
            </Badge>
            <p className="font-medium">No website detected</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Potential Website Development Opportunity — no URL was available to crawl.
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (analysis.analysisStatus === 'failed' || analysis.analysisStatus === 'blocked') {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Website Analysis</CardTitle>
          <CardDescription>Digital presence assessment</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
            <Badge variant="warning" className="mb-3">
              Unavailable
            </Badge>
            <p className="font-medium">Website could not be analyzed</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {analysis.errorMessage || analysis.issues[0]?.label || 'The site was unreachable or blocked.'}
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (analysis.analysisStatus === 'not_analyzed') {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>Website Analysis</CardTitle>
          <CardDescription>Not analyzed yet</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-xl border border-dashed border-border bg-muted/30 p-6 text-center">
            <p className="font-medium">Website detected</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Run Analyze Website to crawl this site and compute deterministic scores.
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const metrics = [
    { label: 'Performance', value: analysis.performance, measured: analysis.performanceMeasured },
    { label: 'Mobile', value: analysis.mobile, measured: analysis.mobileMeasured ?? true },
    { label: 'SEO', value: analysis.seo, measured: analysis.seoMeasured ?? true },
    { label: 'Accessibility', value: analysis.accessibility, measured: analysis.accessibilityMeasured },
  ]

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Website Analysis</CardTitle>
        <CardDescription>
          {analysis.finalUrl ? `Final URL: ${analysis.finalUrl}` : 'Evidence-based technical signals'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground sm:grid-cols-4">
          <Meta label="HTTPS" value={analysis.httpsEnabled == null ? '—' : analysis.httpsEnabled ? 'Yes' : 'No'} />
          <Meta label="Reachable" value={analysis.reachable == null ? '—' : analysis.reachable ? 'Yes' : 'No'} />
          <Meta label="Load time" value={analysis.loadTimeMs != null ? `${analysis.loadTimeMs}ms` : '—'} />
          <Meta
            label="Website score"
            value={analysis.websiteScore != null ? `${analysis.websiteScore}/100` : '—'}
          />
        </div>

        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {metrics.map((m) => {
            if (!m.measured) {
              return (
                <div
                  key={m.label}
                  className="flex flex-col items-center rounded-xl border border-border/70 bg-muted/20 px-2 py-4"
                >
                  <div className="flex h-[84px] w-[84px] items-center justify-center rounded-full border border-dashed border-border text-xs text-muted-foreground">
                    N/A
                  </div>
                  <p className="mt-2 text-xs font-medium text-muted-foreground">{m.label}</p>
                  <p className="text-sm font-semibold">Not measured</p>
                </div>
              )
            }
            const meta = scoreMeta(m.value)
            return (
              <div
                key={m.label}
                className="flex flex-col items-center rounded-xl border border-border/70 bg-muted/20 px-2 py-4"
              >
                <ProgressRing value={m.value} size={84} strokeWidth={7} colorClass={meta.stroke} />
                <p className="mt-2 text-xs font-medium text-muted-foreground">{m.label}</p>
                <p className="text-sm font-semibold tabular-nums">{m.value}/100</p>
                <Badge variant={meta.badge} className="mt-2">
                  {meta.label}
                </Badge>
              </div>
            )
          })}
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <Flag label="Booking system" ok={analysis.hasBooking} />
          <Flag label="Contact form" ok={analysis.hasContactForm} />
          <Flag
            label={analysis.chatbotProvider ? `Chatbot (${analysis.chatbotProvider})` : 'Chatbot'}
            ok={analysis.hasChatbot}
          />
        </div>

        {analysis.technology && analysis.technology.length > 0 ? (
          <div>
            <p className="mb-2 text-sm font-medium">Technology detected</p>
            <div className="flex flex-wrap gap-2">
              {analysis.technology.map((tech) => (
                <Badge key={tech} variant="secondary">
                  {tech}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}

        {analysis.scoreReasons && analysis.scoreReasons.length > 0 ? (
          <div>
            <p className="mb-2 text-sm font-medium">Score reasons</p>
            <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
              {analysis.scoreReasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {analysis.issues.length > 0 ? (
          <div>
            <p className="mb-2 text-sm font-medium">Issues detected</p>
            <div className="flex flex-wrap gap-2">
              {analysis.issues.map((issue) => (
                <Badge
                  key={issue.label}
                  variant={
                    issue.severity === 'high'
                      ? 'destructive'
                      : issue.severity === 'medium'
                        ? 'warning'
                        : 'secondary'
                  }
                >
                  {issue.severity === 'high' ? 'Critical · ' : issue.severity === 'medium' ? 'Warning · ' : ''}
                  {issue.label}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/70 px-3 py-2">
      <p>{label}</p>
      <p className="truncate font-medium text-foreground">{value}</p>
    </div>
  )
}

function Flag({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div
      className={cn(
        'flex items-center gap-3 rounded-lg border border-border px-3 py-2.5 text-sm',
        ok ? 'bg-success/5' : 'bg-muted/40',
      )}
    >
      {ok ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-hidden />
      ) : (
        <XCircle className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
      )}
      <div className="min-w-0">
        <p className="text-muted-foreground">{label}</p>
        <p className="font-medium">{ok ? 'Yes' : 'No'}</p>
      </div>
    </div>
  )
}
