import { apiRequest } from './client'

export type ProviderMode = 'unavailable' | 'mock' | 'test' | 'live' | 'disabled' | 'error'
export type ProviderStatusLabel =
  | 'healthy'
  | 'not_configured'
  | 'test_mode'
  | 'degraded'
  | 'disabled'
  | 'unavailable'
  | 'configured'

export interface ProviderInfo {
  provider?: string
  configured: boolean
  enabled: boolean
  mode: ProviderMode | string
  status: ProviderStatusLabel | string
  healthy?: boolean
  live_tested?: boolean
  degraded?: boolean
  last_checked?: string | null
  last_success?: string | null
  last_error?: string | null
  last_failure?: string | null
  [key: string]: unknown
}

export interface SystemHealthResponse {
  status: string
  app_env: string
  database: { status: string; detail?: string }
  config_ok: boolean
  config_problems?: string[]
  authentication: { status: string; note?: string }
  job_queue: { backend: string; status: string }
  providers: Record<string, ProviderInfo>
}

export interface ConfigValidateResponse {
  app_env: string
  ok: boolean
  error_count: number
  warning_count: number
  items: { code: string; severity: string; message: string; category: string }[]
}

export interface ReadinessResponse {
  app_env: string
  ready: boolean
  blocked_count: number
  warning_count: number
  checklist: { id: string; label?: string; status: string; detail: string }[]
  note?: string
}

export function getSystemHealth() {
  return apiRequest<SystemHealthResponse>('/api/system/health')
}

export function getProviders() {
  return apiRequest<{ app_env: string; providers: Record<string, ProviderInfo> }>('/api/system/providers')
}

export function testProvider(provider: string) {
  return apiRequest<{
    provider: string
    ok: boolean
    message: string
    mode?: string
    status?: string
    side_effects?: string
    live_operation?: boolean
    provider_test?: boolean
    error_code?: string
  }>(`/api/system/providers/${provider}/test`, { method: 'POST' })
}

export function validateConfig() {
  return apiRequest<ConfigValidateResponse>('/api/system/config/validate')
}

export function getReadiness() {
  return apiRequest<ReadinessResponse>('/api/system/readiness')
}

export function getProviderLogs() {
  return apiRequest<{ items: Record<string, unknown>[] }>('/api/system/provider-logs')
}

export function getSystemJobs() {
  return apiRequest<{ items: Record<string, unknown>[] }>('/api/system/jobs')
}

export function getSystemAudit() {
  return apiRequest<{ items: Record<string, unknown>[] }>('/api/system/audit')
}

export interface ProviderMatrixRow {
  provider: string
  configured: boolean
  mode: string
  live_tested: boolean
  healthy?: boolean
  last_checked?: string | null
  last_success?: string | null
  last_error?: string | null
  result: string
}

export function getProviderMatrix() {
  return apiRequest<{ app_env: string; note?: string; providers: ProviderMatrixRow[] }>(
    '/api/system/providers/matrix',
  )
}

export function runProviderE2E(sendEmail = false) {
  const q = sendEmail ? '?send_email=true' : ''
  return apiRequest<{
    provider_test: boolean
    organization_id: string
    organization_slug: string
    lead_id: string
    tested_at: string
    stages: Record<string, unknown>[]
    matrix: unknown
    note?: string
  }>(`/api/system/providers/e2e-test${q}`, { method: 'POST' })
}
