import { Radar } from 'lucide-react'
import { motion } from 'framer-motion'
import { PageHeader } from '@/components/shared/PageHeader'
import { SkeletonCard } from '@/components/shared/Skeleton'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { leadSources } from '@/data/mock'
import { useSimulatedLoading } from '@/hooks/useMediaQuery'
import { formatNumber } from '@/lib/utils'
import { softTransition } from '@/lib/motion'

export function LeadSourcesPage() {
  const { loading } = useSimulatedLoading(600)

  if (loading) {
    return (
      <div className="min-w-0">
        <PageHeader title="Lead Sources" description="Loading sources..." />
        <div className="grid gap-3 sm:grid-cols-2 sm:gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="min-w-0">
      <PageHeader
        title="Lead Sources"
        description="Monitor acquisition channels and lead quality."
        breadcrumbs={[{ label: 'Lead Generation' }, { label: 'Lead Sources' }]}
      />

      <div className="grid gap-3 sm:grid-cols-2 sm:gap-4">
        {leadSources.map((source, i) => (
          <motion.div
            key={source.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...softTransition, delay: i * 0.05 }}
          >
            <Card className="h-full transition-shadow hover:shadow-md">
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                      <Radar className="h-5 w-5" aria-hidden />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{source.name}</p>
                      <p className="text-sm text-muted-foreground">{formatNumber(source.leads)} leads</p>
                    </div>
                  </div>
                  <Badge variant={source.status === 'active' ? 'success' : 'secondary'} className="capitalize">
                    {source.status}
                  </Badge>
                </div>
                <div className="mt-5">
                  <div className="mb-2 flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Quality score</span>
                    <span className="font-medium tabular-nums">{source.quality}%</span>
                  </div>
                  <Progress value={source.quality} />
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
