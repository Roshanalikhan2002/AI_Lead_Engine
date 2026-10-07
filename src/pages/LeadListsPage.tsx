import { ListChecks, Plus } from 'lucide-react'
import { motion } from 'framer-motion'
import { PageHeader } from '@/components/shared/PageHeader'
import { EmptyState } from '@/components/shared/EmptyState'
import { SkeletonCard } from '@/components/shared/Skeleton'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { leadLists } from '@/data/mock'
import { useSimulatedLoading } from '@/hooks/useMediaQuery'
import { useToast } from '@/components/shared/Toast'
import { formatNumber } from '@/lib/utils'
import { softTransition } from '@/lib/motion'

export function LeadListsPage() {
  const { loading } = useSimulatedLoading(650)
  const { toast } = useToast()

  if (loading) {
    return (
      <div className="min-w-0">
        <PageHeader title="Lead Lists" description="Loading lists..." />
        <div className="grid gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    )
  }

  if (leadLists.length === 0) {
    return (
      <EmptyState
        icon={ListChecks}
        title="No lead lists"
        description="Organize leads into targeted lists for outreach campaigns."
        actionLabel="Create List"
        onAction={() => toast({ title: 'Create list (demo)', type: 'info' })}
      />
    )
  }

  return (
    <div className="min-w-0">
      <PageHeader
        title="Lead Lists"
        description="Organize leads into focused audiences for campaigns."
        breadcrumbs={[{ label: 'Lead Generation' }, { label: 'Lead Lists' }]}
        actions={
          <Button onClick={() => toast({ title: 'List created (demo)', type: 'success' })}>
            <Plus className="h-4 w-4" />
            New List
          </Button>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-3">
        {leadLists.map((list, i) => (
          <motion.div
            key={list.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...softTransition, delay: i * 0.04 }}
          >
            <Card className="h-full transition-all hover:-translate-y-0.5 hover:shadow-md">
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <ListChecks className="h-5 w-5" aria-hidden />
                  </div>
                  <p className="text-2xl font-semibold tabular-nums">{formatNumber(list.count)}</p>
                </div>
                <p className="mt-4 font-semibold">{list.name}</p>
                {list.description ? (
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{list.description}</p>
                ) : (
                  <p className="mt-1 text-sm text-muted-foreground">Custom audience list</p>
                )}
                <div className="mt-4 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>Created {new Date(list.createdAt).toLocaleDateString()}</span>
                  <span>Updated {new Date(list.updatedAt).toLocaleDateString()}</span>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
