import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  clearTokens,
  fetchMe,
  getStoredAccessToken,
  getStoredRefreshToken,
  listOrganizations,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  storeTokens,
  switchOrganization,
  type AuthOrganization,
  type AuthUser,
  type MeResponse,
} from '@/api/auth'
import { apiRequest } from '@/api/client'

type AuthState = {
  loading: boolean
  user: AuthUser | null
  organization: AuthOrganization | null
  role: string | null
  permissions: string[]
  organizations: (AuthOrganization & { role: string; active: boolean })[]
  login: (email: string, password: string) => Promise<void>
  register: (payload: {
    email: string
    password: string
    first_name?: string
    last_name?: string
    organization_name?: string
  }) => Promise<void>
  logout: () => Promise<void>
  refreshMe: () => Promise<void>
  switchOrg: (organizationId: string) => Promise<void>
  hasPermission: (permission: string) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

// Patch apiRequest to attach bearer token for authenticated app calls
const originalFetch = globalThis.fetch.bind(globalThis)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [organization, setOrganization] = useState<AuthOrganization | null>(null)
  const [role, setRole] = useState<string | null>(null)
  const [permissions, setPermissions] = useState<string[]>([])
  const [organizations, setOrganizations] = useState<
    (AuthOrganization & { role: string; active: boolean })[]
  >([])

  const applyMe = useCallback(async (me: MeResponse) => {
    setUser(me.user)
    setOrganization(me.organization)
    setRole(me.role)
    setPermissions(me.permissions || [])
    try {
      const orgs = await listOrganizations()
      setOrganizations(orgs)
    } catch {
      setOrganizations([])
    }
  }, [])

  const refreshMe = useCallback(async () => {
    const token = getStoredAccessToken()
    if (!token) {
      setUser(null)
      setOrganization(null)
      setRole(null)
      setPermissions([])
      return
    }
    const me = await fetchMe()
    await applyMe(me)
  }, [applyMe])

  useEffect(() => {
    // Ensure all apiRequest calls include Authorization when present
    globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const token = getStoredAccessToken()
      if (!token) return originalFetch(input, init)
      const headers = new Headers(init?.headers || {})
      if (!headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
      return originalFetch(input, { ...init, headers })
    }
    ;(async () => {
      try {
        await refreshMe()
      } catch {
        clearTokens()
        setUser(null)
      } finally {
        setLoading(false)
      }
    })()
    return () => {
      globalThis.fetch = originalFetch
    }
  }, [refreshMe])

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await apiLogin({ email, password })
      storeTokens(res.access_token, res.refresh_token)
      await applyMe(res)
    },
    [applyMe],
  )

  const register = useCallback(
    async (payload: {
      email: string
      password: string
      first_name?: string
      last_name?: string
      organization_name?: string
    }) => {
      const res = await apiRegister(payload)
      storeTokens(res.access_token, res.refresh_token)
      await applyMe(res)
    },
    [applyMe],
  )

  const logout = useCallback(async () => {
    try {
      await apiLogout(getStoredRefreshToken())
    } catch {
      // ignore
    }
    clearTokens()
    setUser(null)
    setOrganization(null)
    setRole(null)
    setPermissions([])
    setOrganizations([])
  }, [])

  const switchOrg = useCallback(
    async (organizationId: string) => {
      const res = await switchOrganization(organizationId, getStoredRefreshToken())
      storeTokens(res.access_token, res.refresh_token)
      await applyMe(res)
      // Force reload of tenant-scoped UI state
      window.location.assign('/')
    },
    [applyMe],
  )

  const value = useMemo<AuthState>(
    () => ({
      loading,
      user,
      organization,
      role,
      permissions,
      organizations,
      login,
      register,
      logout,
      refreshMe,
      switchOrg,
      hasPermission: (p: string) => permissions.includes(p),
    }),
    [
      loading,
      user,
      organization,
      role,
      permissions,
      organizations,
      login,
      register,
      logout,
      refreshMe,
      switchOrg,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

// silence unused import if tree-shaken oddly
void apiRequest
