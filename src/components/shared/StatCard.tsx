import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import { TrendingDown, TrendingUp } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { cn, formatNumber, formatPercent } from '@/lib/utils'
import { softTransition } from '@/lib/motion'

interface StatCardProps {
  title: string
  value: number
  change?: number
  icon: LucideIcon
  className?: string
  delay?: number
}

export function StatCard({ title, value, change, icon: Icon, className, delay = 0 }: StatCardProps) {
  const positive = (change ?? 0) >= 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...softTransition, delay }}
      whileHover={{ y: -2 }}
    >
      <Card className={cn('group h-full overflow-hidden border-border/80 hover:shadow-md', className)}>
        <CardContent className="p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
              <Icon className="h-5 w-5" aria-hidden />
            </div>
            {change != null ? (
            <div
              className={cn(
                'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium',
                positive ? 'bg-success/10 text-success' : 'bg-destructive/10 text-destructive',
              )}
            >
              {positive ? <TrendingUp className="h-3 w-3" aria-hidden /> : <TrendingDown className="h-3 w-3" aria-hidden />}
              <span>{formatPercent(change)}</span>
            </div>
            ) : null}
          </div>
          <p className="mt-4 text-sm text-muted-foreground">{title}</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">{formatNumber(value)}</p>
        </CardContent>
      </Card>
    </motion.div>
  )
}
