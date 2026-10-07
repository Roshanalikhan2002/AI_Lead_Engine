import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { CSSProperties } from 'react'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('en-US').format(n)
}

export function formatPercent(n: number, digits = 1): string {
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}%`
}

export function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('')
}

export function scoreQuality(value: number): 'good' | 'warning' | 'critical' {
  if (value >= 75) return 'good'
  if (value >= 50) return 'warning'
  return 'critical'
}

export const chartTooltipStyle: CSSProperties = {
  borderRadius: 12,
  border: '1px solid var(--color-border)',
  background: 'var(--color-card)',
  color: 'var(--color-foreground)',
  boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
  fontSize: 12,
}
