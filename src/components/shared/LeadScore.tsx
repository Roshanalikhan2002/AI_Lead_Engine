import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import { scoreLabel, scoreTier } from '@/types'
import { Badge } from '@/components/ui/badge'

interface LeadScoreProps {
  score: number
  showLabel?: boolean
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const tierVariant = {
  hot: 'hot',
  warm: 'warm',
  potential: 'potential',
  low: 'low',
} as const

export function LeadScore({ score, showLabel = true, size = 'md', className }: LeadScoreProps) {
  const unscored = score <= 0
  const tier = scoreTier(score)
  return (
    <div className={cn('inline-flex items-center gap-2', className)}>
      <span
        className={cn(
          'font-semibold tabular-nums',
          size === 'sm' && 'text-sm',
          size === 'md' && 'text-base',
          size === 'lg' && 'text-3xl',
        )}
      >
        {unscored ? '—' : score}
      </span>
      {showLabel ? (
        <Badge variant={unscored ? 'secondary' : tierVariant[tier]}>
          {unscored ? 'Unscored' : scoreLabel(score)}
        </Badge>
      ) : null}
    </div>
  )
}

interface ProgressRingProps {
  value: number
  size?: number
  strokeWidth?: number
  label?: string
  className?: string
  colorClass?: string
}

export function ProgressRing({
  value,
  size = 96,
  strokeWidth = 8,
  label,
  className,
  colorClass = 'stroke-primary',
}: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const [display, setDisplay] = useState(0)
  const offset = circumference - (display / 100) * circumference

  useEffect(() => {
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / 900)
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(value * eased)
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [value])

  return (
    <div className={cn('relative inline-flex flex-col items-center', className)}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className="stroke-muted"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className={colorClass}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.05s linear' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-semibold tabular-nums">{Math.round(display)}</span>
      </div>
      {label ? <p className="mt-2 text-xs font-medium text-muted-foreground">{label}</p> : null}
    </div>
  )
}
