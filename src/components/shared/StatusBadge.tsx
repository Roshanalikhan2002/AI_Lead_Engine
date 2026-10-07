import type { ReactNode } from 'react'
import { Badge } from '@/components/ui/badge'
import type { CampaignStatus, EmailStatus, MeetingStatus, OutreachStatus, ReplyIntent } from '@/types'

const opportunityColors: Record<string, 'default' | 'info' | 'warning' | 'success' | 'secondary'> = {
  'Website Development': 'info',
  'Website Redesign': 'warning',
  'AI Chatbot': 'default',
  'AI Automation': 'default',
  'CRM Automation': 'secondary',
  'Appointment Automation': 'success',
  'E-commerce Development': 'info',
  'Custom Software': 'secondary',
  'Mobile App': 'info',
  'WhatsApp Automation': 'success',
  'AI Voice Agent': 'default',
}

export function OpportunityBadge({ opportunity }: { opportunity: string }) {
  return <Badge variant={opportunityColors[opportunity] ?? 'secondary'}>{opportunity}</Badge>
}

export function EmailStatusBadge({ status }: { status: EmailStatus }) {
  const map = {
    verified: { label: 'Verified', variant: 'success' as const },
    unverified: { label: 'Unverified', variant: 'warning' as const },
    invalid: { label: 'Invalid', variant: 'destructive' as const },
    pending: { label: 'Pending', variant: 'secondary' as const },
  }
  const item = map[status]
  return <Badge variant={item.variant}>{item.label}</Badge>
}

export function OutreachStatusBadge({ status }: { status: OutreachStatus }) {
  const map = {
    not_started: { label: 'Not Generated', variant: 'secondary' as const },
    draft: { label: 'Draft', variant: 'info' as const },
    approved: { label: 'Approved', variant: 'success' as const },
    rejected: { label: 'Rejected', variant: 'destructive' as const },
    edited: { label: 'Edited', variant: 'warning' as const },
    queued: { label: 'Queued', variant: 'info' as const },
    sent: { label: 'Sent', variant: 'default' as const },
    replied: { label: 'Replied', variant: 'success' as const },
    meeting: { label: 'Meeting', variant: 'success' as const },
    bounced: { label: 'Bounced', variant: 'destructive' as const },
  }
  const item = map[status] ?? map.not_started
  return <Badge variant={item.variant}>{item.label}</Badge>
}

export function CampaignStatusBadge({ status }: { status: CampaignStatus }) {
  const map = {
    draft: { label: 'Draft', variant: 'secondary' as const },
    running: { label: 'Running', variant: 'success' as const },
    paused: { label: 'Paused', variant: 'warning' as const },
    completed: { label: 'Completed', variant: 'info' as const },
  }
  const item = map[status]
  return <Badge variant={item.variant}>{item.label}</Badge>
}

export function MeetingStatusBadge({ status }: { status: MeetingStatus }) {
  const map = {
    scheduled: { label: 'Scheduled', variant: 'info' as const },
    completed: { label: 'Completed', variant: 'success' as const },
    cancelled: { label: 'Cancelled', variant: 'secondary' as const },
    no_show: { label: 'No Show', variant: 'destructive' as const },
  }
  const item = map[status]
  return <Badge variant={item.variant}>{item.label}</Badge>
}

export function IntentBadge({ intent, confidence }: { intent: ReplyIntent; confidence?: number }) {
  const map = {
    interested: { label: 'Interested', variant: 'success' as const },
    need_pricing: { label: 'Need Pricing', variant: 'info' as const },
    not_interested: { label: 'Not Interested', variant: 'destructive' as const },
    maybe_later: { label: 'Maybe Later', variant: 'warning' as const },
    meeting_request: { label: 'Meeting Request', variant: 'default' as const },
  }
  const item = map[intent]
  return (
    <div className="inline-flex flex-wrap items-center gap-2">
      <Badge variant={item.variant}>AI Intent: {item.label}</Badge>
      {typeof confidence === 'number' ? (
        <Badge variant="outline">Confidence: {confidence}%</Badge>
      ) : null}
    </div>
  )
}

export function StatusBadge({ children, variant = 'secondary' }: { children: ReactNode; variant?: 'default' | 'secondary' | 'success' | 'warning' | 'destructive' | 'info' }) {
  return <Badge variant={variant}>{children}</Badge>
}
