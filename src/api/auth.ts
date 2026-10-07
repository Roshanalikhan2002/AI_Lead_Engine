import { apiRequest, API_URL } from './client'

const ACCESS_KEY = 'leadflow_access_token'
const REFRESH_KEY = 'leadflow_refresh_token'

export type AuthUser = {
  id: string
  email: string
  first_name: string
  last_name: string
  is_active: boolean
  is_verified: boolean
}

export type AuthOrganization = {
  id: string
  name: string
  slug: string
  timezone: string
  default_currency: string
  status: string
  plan: string
  role?: string
  active?: boolean
}

export type MeResponse = {
  user: AuthUser
  organization: AuthOrganization
  role: string
  permissions: string[]
}

export type TokenResponse = MeResponse & {
  access_token: string
  refresh_token: string
  token_type: string
}

export function getStoredAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY)
}

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY)
}

export function storeTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_KEY, access)
  localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

export async function authRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> | undefined),
  }
  const token = getStoredAccessToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${API_URL}${path}`, { ...init, headers })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const details = await response.json()
      message = details?.error?.message || details?.detail || message
      if (typeof details?.detail === 'object' && details?.detail?.message) {
        message = details.detail.message
      }
    } catch {
      // ignore
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function register(payload: {
  email: string
  password: string
  first_name?: string
  last_name?: string
  organization_name?: string
}) {
  return apiRequest<TokenResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function login(payload: { email: string; password: string }) {
  return apiRequest<TokenResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchMe() {
  return authRequest<MeResponse>('/api/auth/me')
}

export function logout(refresh_token?: string | null) {
  return authRequest<{ status: string }>('/api/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refresh_token || getStoredRefreshToken() }),
  })
}

export function listOrganizations() {
  return authRequest<(AuthOrganization & { role: string; active: boolean })[]>('/api/organizations')
}

export function switchOrganization(organizationId: string, refresh_token?: string | null) {
  return authRequest<TokenResponse>(`/api/organizations/${organizationId}/switch`, {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refresh_token || getStoredRefreshToken() }),
  })
}

export function forgotPassword(email: string) {
  return apiRequest<{ status: string; message: string; reset_token?: string }>(
    '/api/auth/forgot-password',
    { method: 'POST', body: JSON.stringify({ email }) },
  )
}

export function resetPassword(token: string, new_password: string) {
  return apiRequest<{ status: string }>('/api/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ token, new_password }),
  })
}

export function acceptInvite(payload: {
  token: string
  password?: string
  first_name?: string
  last_name?: string
}) {
  return apiRequest<TokenResponse>('/api/auth/invitations/accept', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function peekInvite(token: string) {
  return apiRequest<{ email: string; role: string; organization_name: string | null }>(
    `/api/auth/invitations/${token}`,
  )
}

export function listTeam() {
  return authRequest<
    {
      id: string
      email: string
      first_name: string
      last_name: string
      role: string
      status: string
      joined_at: string | null
    }[]
  >('/api/team')
}

export function inviteTeamMember(email: string, role: string) {
  return authRequest<{
    id: string
    email: string
    role: string
    email_sent: boolean
    message: string
    invite_token?: string
  }>('/api/team/invite', { method: 'POST', body: JSON.stringify({ email, role }) })
}
