import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/api/client'
import { bookMeeting, getPublicBooking, listMeetingSlots, type BookingPublic, type TimeSlot } from '@/api/meetings'

export function PublicBookingPage() {
  const { token } = useParams<{ token: string }>()
  const [booking, setBooking] = useState<BookingPublic | null>(null)
  const [slots, setSlots] = useState<TimeSlot[]>([])
  const [error, setError] = useState<string | null>(null)
  const [step, setStep] = useState(1)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState<{
    start_at: string
    timezone: string
    title: string
    meeting_url: string | null
  } | null>(null)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    ;(async () => {
      try {
        const b = await getPublicBooking(token)
        if (cancelled) return
        setBooking(b)
        const start = new Date()
        const end = new Date()
        end.setDate(end.getDate() + 14)
        const s = await listMeetingSlots({
          meeting_type_id: b.meeting_type.id,
          start_date: start.toISOString().slice(0, 10),
          end_date: end.toISOString().slice(0, 10),
          timezone: b.timezone,
        })
        if (!cancelled) setSlots(s)
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Invalid booking link')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token])

  const dates = useMemo(() => {
    const set = new Set<string>()
    for (const s of slots) {
      set.add(new Date(s.start_at).toISOString().slice(0, 10))
    }
    return Array.from(set).sort()
  }, [slots])

  const daySlots = useMemo(() => {
    if (!selectedDate) return []
    return slots.filter((s) => new Date(s.start_at).toISOString().slice(0, 10) === selectedDate)
  }, [selectedDate, slots])

  async function confirm() {
    if (!token || !selectedSlot || !booking) return
    setSaving(true)
    try {
      const meeting = await bookMeeting({
        token,
        start_at: selectedSlot.start_at,
        timezone: booking.timezone,
        prospect_name: name,
        prospect_email: email,
        prospect_message: message || null,
        idempotency_key: `public:${token}:${selectedSlot.start_at}:${email.toLowerCase()}`,
      })
      setDone({
        start_at: meeting.start_at,
        timezone: meeting.timezone,
        title: meeting.title,
        meeting_url: meeting.meeting_url,
      })
      setStep(5)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Booking failed')
    } finally {
      setSaving(false)
    }
  }

  if (error && !booking) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-lg items-center px-4">
        <Card className="w-full">
          <CardHeader>
            <CardTitle>Booking unavailable</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  if (!booking) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-lg items-center px-4 text-sm text-muted-foreground">
        Loading booking…
      </div>
    )
  }

  if (done) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-lg items-center px-4">
        <Card className="w-full">
          <CardHeader>
            <CardTitle>Your meeting is scheduled.</CardTitle>
            <CardDescription>{done.title}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>
              <span className="text-muted-foreground">When:</span>{' '}
              {new Date(done.start_at).toLocaleString()} ({done.timezone})
            </p>
            <p>
              <span className="text-muted-foreground">Type:</span> {booking.meeting_type.name}
            </p>
            {done.meeting_url ? (
              <p>
                <a className="text-primary underline" href={done.meeting_url}>
                  Join link
                </a>
              </p>
            ) : (
              <p className="text-muted-foreground">No meeting URL — calendar provider is not live.</p>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto min-h-dvh max-w-lg px-4 py-10">
      <div className="mb-6">
        <p className="text-sm text-muted-foreground">LeadFlow AI</p>
        <h1 className="text-2xl font-semibold tracking-tight">{booking.meeting_type.name}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {booking.meeting_type.duration_minutes} minutes · {booking.timezone}
        </p>
        {booking.meeting_type.description ? (
          <p className="mt-2 text-sm">{booking.meeting_type.description}</p>
        ) : null}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {step === 1 && 'Select a date'}
            {step === 2 && 'Select a time'}
            {step === 3 && 'Your details'}
            {step === 4 && 'Confirm'}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <p className="text-sm text-destructive">{error}</p> : null}

          {step === 1 && (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {dates.length === 0 ? (
                <p className="col-span-full text-sm text-muted-foreground">No available dates.</p>
              ) : (
                dates.map((d) => (
                  <Button
                    key={d}
                    variant={selectedDate === d ? 'default' : 'outline'}
                    onClick={() => {
                      setSelectedDate(d)
                      setSelectedSlot(null)
                      setStep(2)
                    }}
                  >
                    {d}
                  </Button>
                ))
              )}
            </div>
          )}

          {step === 2 && (
            <div className="grid grid-cols-2 gap-2">
              {daySlots.map((s) => (
                <Button
                  key={s.start_at}
                  variant={selectedSlot?.start_at === s.start_at ? 'default' : 'outline'}
                  onClick={() => {
                    setSelectedSlot(s)
                    setStep(3)
                  }}
                >
                  {new Date(s.start_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </Button>
              ))}
              <Button variant="ghost" className="col-span-full" onClick={() => setStep(1)}>
                Back
              </Button>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="msg">Message (optional)</Label>
                <Textarea id="msg" value={message} onChange={(e) => setMessage(e.target.value)} rows={3} />
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setStep(2)}>
                  Back
                </Button>
                <Button disabled={!name.trim() || !email.trim()} onClick={() => setStep(4)}>
                  Continue
                </Button>
              </div>
            </div>
          )}

          {step === 4 && selectedSlot && (
            <div className="space-y-3 text-sm">
              <p>
                {selectedDate} ·{' '}
                {new Date(selectedSlot.start_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}{' '}
                ({booking.timezone})
              </p>
              <p>
                {name} · {email}
              </p>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setStep(3)}>
                  Back
                </Button>
                <Button disabled={saving} onClick={() => void confirm()}>
                  {saving ? 'Booking…' : 'Confirm Meeting'}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      <p className="mt-4 text-center text-xs text-muted-foreground">
        Calendar live: {booking.calendar_live ? 'yes' : 'no'}
      </p>
    </div>
  )
}
