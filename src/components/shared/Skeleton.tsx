import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {}

export function Skeleton({ className, ...props }: SkeletonProps) {
  return <div className={cn('relative overflow-hidden rounded-md bg-muted shimmer', className)} {...props} />
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-xl border border-border bg-card p-4 sm:p-5', className)}>
      <div className="flex items-start justify-between">
        <Skeleton className="h-10 w-10 rounded-lg" />
        <Skeleton className="h-5 w-12 rounded-md" />
      </div>
      <Skeleton className="mt-4 h-3 w-20" />
      <Skeleton className="mt-2 h-7 w-28" />
    </div>
  )
}

export function SkeletonChart({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-xl border border-border bg-card p-5', className)}>
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-2 h-3 w-56 max-w-full" />
      <Skeleton className="mt-6 h-48 w-full rounded-lg sm:h-52" />
    </div>
  )
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="border-b border-border p-4">
        <Skeleton className="h-4 w-48 max-w-full" />
      </div>
      <div className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 p-4">
            <Skeleton className="h-9 w-9 shrink-0 rounded-full" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-3.5 w-1/3 max-w-48" />
              <Skeleton className="h-3 w-1/4 max-w-32" />
            </div>
            <Skeleton className="hidden h-6 w-16 rounded-md sm:block" />
            <Skeleton className="hidden h-6 w-20 rounded-md md:block" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function SkeletonLeadCard() {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-3">
        <Skeleton className="h-11 w-11 shrink-0 rounded-full" />
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-4 w-36 max-w-full" />
          <Skeleton className="h-3 w-24" />
        </div>
        <Skeleton className="h-6 w-14 rounded-md" />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
      </div>
    </div>
  )
}

export function SkeletonProfile() {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-card p-5 sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <Skeleton className="h-16 w-16 shrink-0 rounded-2xl" />
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-6 w-48 max-w-full" />
            <Skeleton className="h-4 w-64 max-w-full" />
          </div>
          <Skeleton className="h-10 w-28 rounded-lg" />
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <SkeletonChart />
        <SkeletonChart />
      </div>
    </div>
  )
}

export function SkeletonDashboard() {
  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <SkeletonChart />
        <SkeletonChart />
      </div>
      <SkeletonTable />
    </div>
  )
}
