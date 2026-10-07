import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import {
  acceptInvite,
  forgotPassword,
  peekInvite,
  resetPassword,
  storeTokens,
} from '@/api/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function LoginPage() {
  const { login, user, loading } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!loading && user) return <Navigate to="/" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Sign in" subtitle="Access your agency workspace">
      <form className="space-y-4" onSubmit={onSubmit}>
        <Field label="Email">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field label="Password">
          <PasswordInput
            value={password}
            onChange={setPassword}
            required
            minLength={8}
          />
        </Field>
        {error && <p className="text-sm text-rose-700">{error}</p>}
        <Button className="w-full" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted-foreground">
        <Link className="underline" to="/forgot-password">
          Forgot password?
        </Link>
        {' · '}
        <Link className="underline" to="/register">
          Create account
        </Link>
      </p>
    </AuthShell>
  )
}

export function RegisterPage() {
  const { register, user, loading } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    organization_name: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!loading && user) return <Navigate to="/" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await register(form)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Create account" subtitle="Start a new agency workspace">
      <form className="space-y-4" onSubmit={onSubmit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="First name">
            <Input
              value={form.first_name}
              onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))}
            />
          </Field>
          <Field label="Last name">
            <Input
              value={form.last_name}
              onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))}
            />
          </Field>
        </div>
        <Field label="Work email">
          <Input
            type="email"
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            required
          />
        </Field>
        <Field label="Organization name">
          <Input
            value={form.organization_name}
            onChange={(e) => setForm((f) => ({ ...f, organization_name: e.target.value }))}
            placeholder="Acme Agency"
          />
        </Field>
        <Field label="Password">
          <PasswordInput
            value={form.password}
            onChange={(value) => setForm((f) => ({ ...f, password: value }))}
            required
            minLength={8}
            placeholder="At least 8 characters"
          />
        </Field>
        {error && <p className="text-sm text-rose-700">{error}</p>}
        <Button className="w-full" disabled={busy}>
          {busy ? 'Creating…' : 'Create account'}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted-foreground">
        Already have an account?{' '}
        <Link className="underline" to="/login">
          Sign in
        </Link>
      </p>
    </AuthShell>
  )
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      const res = await forgotPassword(email)
      setMessage(res.message + (res.reset_token ? ` Dev token: ${res.reset_token}` : ''))
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Forgot password" subtitle="If the account exists, reset instructions are prepared">
      <form className="space-y-4" onSubmit={onSubmit}>
        <Field label="Email">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        {message && <p className="text-sm text-muted-foreground">{message}</p>}
        <Button className="w-full" disabled={busy}>
          Continue
        </Button>
      </form>
      <p className="mt-4 text-center text-sm">
        <Link className="underline" to="/login">
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  )
}

export function ResetPasswordPage() {
  const [token, setToken] = useState(() => new URLSearchParams(window.location.search).get('token') || '')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const navigate = useNavigate()

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    try {
      await resetPassword(token, password)
      setMessage('Password updated. You can sign in.')
      setTimeout(() => navigate('/login'), 1200)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Reset failed')
    }
  }

  return (
    <AuthShell title="Reset password" subtitle="Choose a new password">
      <form className="space-y-4" onSubmit={onSubmit}>
        <Field label="Reset token">
          <Input value={token} onChange={(e) => setToken(e.target.value)} required />
        </Field>
        <Field label="New password">
          <PasswordInput
            value={password}
            onChange={setPassword}
            required
            minLength={8}
          />
        </Field>
        {message && <p className="text-sm text-muted-foreground">{message}</p>}
        <Button className="w-full">Update password</Button>
      </form>
    </AuthShell>
  )
}

export function InviteAcceptPage() {
  const { token = '' } = useParams()
  const [info, setInfo] = useState<{ email: string; organization_name: string | null } | null>(null)
  const [password, setPassword] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    peekInvite(token)
      .then((res) => setInfo({ email: res.email, organization_name: res.organization_name }))
      .catch(() => setError('Invitation not found or expired'))
  }, [token])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    try {
      const res = await acceptInvite({
        token,
        password: password || undefined,
        first_name: firstName,
        last_name: lastName,
      })
      storeTokens(res.access_token, res.refresh_token)
      navigate('/', { replace: true })
      window.location.reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not accept invitation')
    }
  }

  return (
    <AuthShell
      title="Join organization"
      subtitle={info ? `${info.organization_name || 'Organization'} · ${info.email}` : 'Accept your invite'}
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        <Field label="First name">
          <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
        </Field>
        <Field label="Last name">
          <Input value={lastName} onChange={(e) => setLastName(e.target.value)} />
        </Field>
        <Field label="Password (required for new accounts)">
          <PasswordInput value={password} onChange={setPassword} minLength={8} />
        </Field>
        {error && <p className="text-sm text-rose-700">{error}</p>}
        <Button className="w-full">Accept invitation</Button>
      </form>
    </AuthShell>
  )
}

function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-100 via-white to-slate-200 px-4">
      <div className="w-full max-w-md rounded-2xl border border-border bg-background/95 p-6 shadow-sm backdrop-blur">
        <div className="mb-6 text-center">
          <p className="text-lg font-semibold tracking-tight">LeadFlow AI</p>
          <h1 className="mt-2 text-2xl font-semibold">{title}</h1>
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        </div>
        {children}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      {children}
    </div>
  )
}

function PasswordInput({
  value,
  onChange,
  placeholder,
  required,
  minLength,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  required?: boolean
  minLength?: number
}) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="relative">
      <Input
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        minLength={minLength}
        placeholder={placeholder}
        className="pr-10"
        autoComplete="current-password"
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute inset-y-0 right-0 flex items-center px-3 text-muted-foreground hover:text-foreground"
        aria-label={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  )
}
