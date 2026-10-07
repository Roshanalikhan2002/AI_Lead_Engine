import { apiRequest } from './client'

export type PlanInfo = {
  id: string
  name: string
  description: string
  monthly_price: number | null
  annual_price: number | null
  currency: string
  limits: Record<string, number | null>
  features: string[]
  contact_sales: boolean
}

export type UsageItem = {
  resource: string
  used: number
  limit: number | null
  remaining: number | null
  percent: number | null
  unlimited: boolean
}

export type SubscriptionInfo = {
  organization_id: string
  plan: string
  organization_plan: string
  status: string
  provider: string
  billing_interval: string
  trial_start: string | null
  trial_end: string | null
  current_period_start: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
  cancelled_at: string | null
  grace_period_ends_at: string | null
  grace_warning: boolean
  plan_name: string
  features: string[]
  billing_provider_configured: boolean
  billing_provider_name: string
  billing_test_mode: boolean
}

export type UsageResponse = {
  plan: string
  plan_name: string
  period_start: string
  period_end: string
  items: UsageItem[]
  subscription: SubscriptionInfo
}

export function listBillingPlans() {
  return apiRequest<{ plans: PlanInfo[] }>('/api/billing/plans')
}

export function getBillingSubscription() {
  return apiRequest<SubscriptionInfo>('/api/billing/subscription')
}

export function getBillingUsage() {
  return apiRequest<UsageResponse>('/api/billing/usage')
}

export function startCheckout(target_plan: string, billing_interval: string = 'month') {
  return apiRequest<{
    provider: string
    mode: string
    checkout_url: string | null
    session_id: string | null
    message: string
  }>('/api/billing/checkout', {
    method: 'POST',
    body: JSON.stringify({ target_plan, billing_interval }),
  })
}

export function openBillingPortal() {
  return apiRequest<{
    provider: string
    mode: string
    portal_url: string | null
    message: string
  }>('/api/billing/portal', { method: 'POST' })
}

export function changePlan(target_plan: string, billing_interval: string = 'month') {
  return apiRequest<SubscriptionInfo>('/api/billing/change-plan', {
    method: 'POST',
    body: JSON.stringify({ target_plan, billing_interval }),
  })
}

export function cancelSubscription(cancel_at_period_end = true) {
  return apiRequest<SubscriptionInfo>('/api/billing/cancel', {
    method: 'POST',
    body: JSON.stringify({ cancel_at_period_end }),
  })
}

export function resumeSubscription() {
  return apiRequest<SubscriptionInfo>('/api/billing/resume', { method: 'POST' })
}

export function usageLimitMessage(resource: string): string {
  const labels: Record<string, string> = {
    leads_discovered: "You've reached your monthly lead discovery limit.",
    website_analyses: "You've reached your monthly website analysis limit.",
    emails_discovered: "You've reached your monthly email discovery limit.",
    emails_verified: "You've reached your monthly email verification limit.",
    ai_qualifications: "You've reached your monthly AI qualification limit.",
    ai_generations: "You've reached your monthly AI generation limit.",
    emails_sent: "You've reached your monthly email send limit.",
    meetings_booked: "You've reached your monthly meetings limit.",
    team_members: "You've reached your team member limit.",
    active_campaigns: "You've reached your active campaign limit.",
  }
  return labels[resource] || "You've reached a plan usage limit."
}

export function upgradeCta(resource: string): string {
  if (resource.startsWith('ai_')) return 'Upgrade for more AI qualifications'
  if (resource === 'leads_discovered') return 'Upgrade to discover more leads'
  if (resource === 'active_campaigns') return 'Upgrade for more campaigns'
  if (resource === 'emails_sent') return 'Upgrade to send more emails'
  return 'Upgrade Plan'
}
