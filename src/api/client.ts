const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  details?: unknown

  constructor(message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let details: unknown
  let message = `Request failed (${response.status})`
  try {
    details = await response.json()
    if (details && typeof details === 'object') {
      const obj = details as { error?: { message?: string; code?: string }; detail?: unknown }
      if (Array.isArray(obj.detail)) {
        const parts = (obj.detail as { loc?: unknown[]; msg?: string }[])
          .map((item) => {
            const field = Array.isArray(item.loc)
              ? item.loc.filter((p) => p !== 'body').join('.')
              : ''
            const msg = item.msg || 'Invalid value'
            return field ? `${field}: ${msg}` : msg
          })
          .filter(Boolean)
        message = parts.length ? parts.join(' · ') : obj.error?.message || 'Request validation failed.'
      } else if (obj.error?.message && obj.error.message !== 'Request validation failed.') {
        message = obj.error.message
      } else if (typeof obj.detail === 'string') {
        message = obj.detail
      } else if (obj.error?.message) {
        message = obj.error.message
      } else if (obj.detail && typeof obj.detail === 'object') {
        const detail = obj.detail as {
          message?: unknown
          error?: { message?: string; code?: string; resource?: string; limit?: number; used?: number }
        }
        if (detail.error?.message) {
          message = detail.error.message
        } else if (detail.message) {
          message = String(detail.message)
        }
      }
    }
  } catch {
    // ignore
  }
  return new ApiError(message, response.status, details)
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> | undefined),
  }
  try {
    const { getStoredAccessToken } = await import('./auth')
    const token = getStoredAccessToken()
    if (token) headers.Authorization = `Bearer ${token}`
  } catch {
    // auth module unavailable
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    throw await parseError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export { API_URL }
