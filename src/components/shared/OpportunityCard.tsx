import { motion } from 'framer-motion'
import { Badge } from '@/components/ui/badge'
import { OpportunityBadge } from '@/components/shared/StatusBadge'
import type { Opportunity } from '@/types'
import { softTransition } from '@/lib/motion'
import { cn } from '@/lib/utils'

interface OpportunityCardProps {
  opportunity: Opportunity
  index?: number
  className?: string
}

export function OpportunityCard({ opportunity, index = 0, className }: OpportunityCardProps) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...softTransition, delay: index * 0.05 }}
      className={cn(
        'rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary/30 hover:bg-muted/20',
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">{opportunity.name}</p>
          <div className="mt-1.5">
            <OpportunityBadge opportunity={opportunity.name} />
          </div>
        </div>
        <Badge variant="outline" className="tabular-nums">
          {opportunity.confidence}% confidence
        </Badge>
      </div>

      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
        <motion.div
          className="h-full rounded-full bg-primary"
          initial={{ width: 0 }}
          animate={{ width: `${opportunity.confidence}%` }}
          transition={{ duration: 0.8, ease: 'easeOut', delay: 0.1 + index * 0.05 }}
        />
      </div>

      <p className="mt-3 text-sm leading-relaxed text-foreground">{opportunity.reason}</p>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
        <span className="font-medium text-foreground/80">Evidence:</span> {opportunity.evidence}
      </p>
      <p className="mt-3 rounded-lg bg-primary/5 px-3 py-2 text-sm text-primary">
        <span className="font-medium">Recommended:</span> {opportunity.recommendedService}
      </p>
    </motion.article>
  )
}
