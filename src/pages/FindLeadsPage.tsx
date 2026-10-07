import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import type { ReactNode } from 'react'
import {
  Bot,
  Calendar,
  Check,
  Code2,
  Database,
  Globe,
  Loader2,
  MessageCircle,
  Paintbrush,
  PhoneCall,
  ShoppingCart,
  Smartphone,
  Sparkles,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Slider } from '@/components/ui/slider'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { citiesByRegion, countries, industries, opportunityOptions, regionsByCountry } from '@/data/mock'
import { cn, formatNumber } from '@/lib/utils'
import { useToast } from '@/components/shared/Toast'
import { softTransition } from '@/lib/motion'
import { ApiError } from '@/api/client'
import { createGeneration, getGenerationStatus } from '@/api/generation'
import type { WebsiteFilter } from '@/api/generation'

const iconMap: Record<string, LucideIcon> = {
  Globe,
  Paintbrush,
  ShoppingCart,
  Bot,
  Sparkles,
  Database,
  Calendar,
  MessageCircle,
  Code2,
  Smartphone,
  PhoneCall,
}

const stages = [
  'Discovering Businesses',
  'Analyzing Websites',
  'Finding Opportunities',
  'Scoring Leads',
  'Preparing Results',
]

export function FindLeadsPage() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [country, setCountry] = useState('USA')
  const [state, setState] = useState('Texas')
  const [city, setCity] = useState('Austin')
  const [industry, setIndustry] = useState('Dental Clinics')
  const [keywords, setKeywords] = useState('dental clinic, cosmetic dentistry')
  const [size, setSize] = useState('any')
  const [minReviews, setMinReviews] = useState('50')
  const [minRating, setMinRating] = useState('4.0')
  const [hasWebsite, setHasWebsite] = useState('any')
  const [websiteQuality, setWebsiteQuality] = useState('any')
  const [selectedOps, setSelectedOps] = useState<string[]>(['website-redesign', 'appointment'])
  const [quantity, setQuantity] = useState([250])
  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusLabel, setStatusLabel] = useState('Discovering Businesses')
  const [foundCount, setFoundCount] = useState(0)
  const [savedCount, setSavedCount] = useState(0)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const regions = regionsByCountry[country] ?? []
  const cities = citiesByRegion[state] ?? []

  const estimates = useMemo(() => {
    const qty = quantity[0] ?? 250
    return {
      discover: Math.round(qty * 1.8),
      analyze: Math.round(qty * 1.2),
      minutes: Math.max(2, Math.round(qty / 180)),
    }
  }, [quantity])

  const toggleOp = (id: string) => {
    setSelectedOps((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const handleGenerate = async () => {
    setGenerating(true)
    setProgress(0)
    setStatusLabel('Discovering Businesses')
    setFoundCount(0)
    setSavedCount(0)
    setErrorMessage(null)

    const websiteFilter: WebsiteFilter =
      hasWebsite === 'yes' ? 'yes' : hasWebsite === 'no' ? 'no' : 'any'

    try {
      const created = await createGeneration({
        country,
        state,
        city,
        industry,
        keywords: keywords || null,
        min_rating: Number(minRating) || null,
        min_reviews: Number(minReviews) || null,
        website_filter: websiteFilter,
        quantity: quantity[0] ?? 250,
      })

      let done = false
      while (!done) {
        await new Promise((r) => window.setTimeout(r, 1200))
        const status = await getGenerationStatus(created.job_id)
        setFoundCount(status.found)
        setSavedCount(status.saved)
        setProgress(status.progress)
        setStatusLabel(
          status.status === 'pending'
            ? 'Queued — starting discovery'
            : status.status === 'running'
              ? 'Discovering Businesses'
              : status.status === 'completed'
                ? 'Preparing Results'
                : 'Discovery failed',
        )

        if (status.status === 'completed') {
          done = true
          setProgress(100)
          toast({
            title: 'Leads discovered',
            description: `${formatNumber(status.saved)} leads saved from Google Places.`,
            type: 'success',
          })
          window.setTimeout(() => {
            setGenerating(false)
            navigate('/leads')
          }, 600)
        } else if (status.status === 'failed' || status.status === 'cancelled') {
          done = true
          setErrorMessage(status.error_message || 'Lead generation failed.')
          setGenerating(false)
          toast({
            title: 'Generation failed',
            description: status.error_message || 'Please check backend configuration and try again.',
            type: 'error',
          })
        }
      }
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Unable to reach the API. Confirm the backend is running and VITE_API_URL is set.'
      setErrorMessage(message)
      setGenerating(false)
      toast({ title: 'Generation error', description: message, type: 'error' })
    }
  }

  const generationPanel = (
    <Card className="overflow-hidden ring-1 ring-primary/10">
      <div className="gradient-mesh border-b border-border p-5">
        <div className="flex items-center gap-2 text-primary">
          <Sparkles className="h-5 w-5" aria-hidden />
          <p className="text-sm font-semibold">AI Generation</p>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Estimated process for {formatNumber(quantity[0] ?? 250)} leads in {city}, {country}.
        </p>
      </div>
      <CardContent className="space-y-4 p-5">
        <EstimateRow label="Businesses to discover" value={formatNumber(estimates.discover)} />
        <EstimateRow label="Websites to analyze" value={formatNumber(estimates.analyze)} />
        <EstimateRow label="Estimated processing time" value={`~${estimates.minutes} min`} />
        <EstimateRow label="Opportunities selected" value={String(selectedOps.length)} />

        <AnimatePresence mode="wait">
          {generating || errorMessage ? (
            <motion.div
              key="progress"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="space-y-3 rounded-xl border border-primary/20 bg-primary/5 p-4"
              role="status"
              aria-live="polite"
            >
              {errorMessage ? (
                <p className="text-sm text-destructive">{errorMessage}</p>
              ) : (
                <>
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="inline-flex min-w-0 items-center gap-2 font-medium">
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" aria-hidden />
                      <span className="truncate">{statusLabel}</span>
                    </span>
                    <span className="shrink-0 tabular-nums text-muted-foreground">{Math.round(progress)}%</span>
                  </div>
                  <Progress value={progress} />
                  <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                    <span>Found: {formatNumber(foundCount)}</span>
                    <span className="text-right">Saved: {formatNumber(savedCount)}</span>
                  </div>
                  <div className="space-y-2">
                    {stages.map((s, i) => {
                      const done = i === 0 && progress >= 100
                      const active = i === 0 && generating && progress < 100
                      const future = i > 0
                      return (
                        <div
                          key={s}
                          className={cn(
                            'flex items-center gap-2 text-xs transition-colors',
                            done && 'text-success',
                            active && 'font-medium text-foreground',
                            future && 'text-muted-foreground',
                          )}
                        >
                          <span
                            className={cn(
                              'flex h-4 w-4 shrink-0 items-center justify-center rounded-full',
                              done && 'bg-success text-white',
                              active && 'bg-primary text-primary-foreground',
                              future && 'border border-border',
                            )}
                          >
                            {done ? <Check className="h-2.5 w-2.5" /> : null}
                            {active ? <span className="h-1.5 w-1.5 rounded-full bg-current" /> : null}
                          </span>
                          <span className="min-w-0 flex-1 truncate">{s}</span>
                          {future ? <span className="text-[10px] uppercase tracking-wide">Later</span> : null}
                          {i === 0 && generating ? (
                            <span className="tabular-nums">{Math.round(progress)}%</span>
                          ) : null}
                          {i === 0 && done ? <span className="tabular-nums">100%</span> : null}
                        </div>
                      )
                    })}
                  </div>
                  <p className="text-[11px] leading-relaxed text-muted-foreground">
                    Phase 1 runs Google Places discovery only. Website analysis, AI scoring, and outreach stages will
                    activate in later phases.
                  </p>
                </>
              )}
            </motion.div>
          ) : null}
        </AnimatePresence>

        <Button
          size="lg"
          className="w-full shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/25"
          loading={generating}
          onClick={handleGenerate}
        >
          {!generating ? <Sparkles className="h-4 w-4" /> : null}
          {generating ? 'Generating…' : 'Generate Leads'}
        </Button>
        <p className="text-center text-[11px] leading-relaxed text-muted-foreground">
          AI will discover businesses, analyze websites, score opportunities, and prepare your lead list.
        </p>
      </CardContent>
    </Card>
  )

  return (
    <div className="min-w-0 pb-24 xl:pb-0">
      <PageHeader
        title="Find New Leads"
        description="Define your target market and let LeadFlow AI discover high-potential businesses."
        breadcrumbs={[{ label: 'Lead Generation' }, { label: 'Find Leads' }]}
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(260px,320px)]">
        <div className="min-w-0 space-y-5 sm:space-y-6">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={softTransition}>
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
                    1
                  </span>
                  <CardTitle>Target Market</CardTitle>
                </div>
                <CardDescription>Where and who you want to reach</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="Country">
                  <Select
                    value={country}
                    onValueChange={(v) => {
                      setCountry(v)
                      const nextRegions = regionsByCountry[v] ?? []
                      setState(nextRegions[0] ?? '')
                      setCity((citiesByRegion[nextRegions[0] ?? ''] ?? [])[0] ?? '')
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {countries.map((c) => (
                        <SelectItem key={c} value={c}>
                          {c}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="State / Region">
                  <Select
                    value={state}
                    onValueChange={(v) => {
                      setState(v)
                      setCity((citiesByRegion[v] ?? [])[0] ?? '')
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {regions.map((r) => (
                        <SelectItem key={r} value={r}>
                          {r}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="City">
                  <Select value={city} onValueChange={setCity}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {cities.map((c) => (
                        <SelectItem key={c} value={c}>
                          {c}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Industry" className="sm:col-span-2">
                  <Select value={industry} onValueChange={setIndustry}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {industries.map((i) => (
                        <SelectItem key={i} value={i}>
                          {i}
                        </SelectItem>
                      ))}
                      <SelectItem value="Custom Industry">Custom Industry</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Keywords" className="sm:col-span-2 lg:col-span-3">
                  <Input
                    value={keywords}
                    onChange={(e) => setKeywords(e.target.value)}
                    placeholder="e.g. dental, implants, orthodontics"
                  />
                </Field>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ ...softTransition, delay: 0.05 }}>
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
                    2
                  </span>
                  <CardTitle>Business Criteria</CardTitle>
                </div>
                <CardDescription>Filter by size, reputation, and web presence</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="Business size">
                  <Select value={size} onValueChange={setSize}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">Any</SelectItem>
                      <SelectItem value="small">Small</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="large">Large</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Minimum reviews">
                  <Input type="number" value={minReviews} onChange={(e) => setMinReviews(e.target.value)} />
                </Field>
                <Field label="Minimum rating">
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    max="5"
                    value={minRating}
                    onChange={(e) => setMinRating(e.target.value)}
                  />
                </Field>
                <Field label="Has website">
                  <Select value={hasWebsite} onValueChange={setHasWebsite}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">Any</SelectItem>
                      <SelectItem value="yes">Yes</SelectItem>
                      <SelectItem value="no">No</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Website quality">
                  <Select value={websiteQuality} onValueChange={setWebsiteQuality}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">Any</SelectItem>
                      <SelectItem value="poor">Poor</SelectItem>
                      <SelectItem value="average">Average</SelectItem>
                      <SelectItem value="good">Good</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ ...softTransition, delay: 0.1 }}>
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
                    3
                  </span>
                  <CardTitle>Opportunity Filters</CardTitle>
                </div>
                <CardDescription>Select the services you want to sell · {selectedOps.length} selected</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
                  {opportunityOptions.map((op) => {
                    const Icon = iconMap[op.icon] ?? Sparkles
                    const selected = selectedOps.includes(op.id)
                    return (
                      <motion.button
                        key={op.id}
                        type="button"
                        whileTap={{ scale: 0.98 }}
                        aria-pressed={selected}
                        onClick={() => toggleOp(op.id)}
                        className={cn(
                          'relative rounded-xl border p-4 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                          selected
                            ? 'border-primary bg-primary/5 shadow-sm'
                            : 'border-border bg-card hover:border-primary/40 hover:bg-muted/40',
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className={cn(
                              'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
                              selected ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground',
                            )}
                          >
                            <Icon className="h-5 w-5" aria-hidden />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="font-medium leading-snug">{op.name}</p>
                            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{op.description}</p>
                          </div>
                          {selected ? (
                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                              <Check className="h-3 w-3" aria-hidden />
                            </span>
                          ) : null}
                        </div>
                      </motion.button>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ ...softTransition, delay: 0.15 }}>
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
                    4
                  </span>
                  <CardTitle>Lead Quantity</CardTitle>
                </div>
                <CardDescription>How many leads should AI generate?</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="mb-4 flex items-end justify-between gap-3">
                  <p className="text-sm text-muted-foreground">50 — 5,000</p>
                  <p className="text-3xl font-semibold tabular-nums text-primary">{formatNumber(quantity[0] ?? 250)}</p>
                </div>
                <Slider
                  value={quantity}
                  onValueChange={setQuantity}
                  min={50}
                  max={5000}
                  step={50}
                  aria-label="Lead quantity"
                />
              </CardContent>
            </Card>
          </motion.div>

          <div className="xl:hidden">{generationPanel}</div>
        </div>

        <div className="hidden xl:sticky xl:top-24 xl:block xl:self-start">{generationPanel}</div>
      </div>

      {/* Mobile sticky CTA */}
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-background/95 p-3 backdrop-blur xl:hidden safe-px">
        <Button
          size="lg"
          className="w-full shadow-md shadow-primary/20"
          loading={generating}
          onClick={handleGenerate}
        >
          {!generating ? <Sparkles className="h-4 w-4" /> : null}
          {generating ? `Generating… ${Math.round(progress)}%` : `Generate ${formatNumber(quantity[0] ?? 250)} Leads`}
        </Button>
      </div>
    </div>
  )
}

function Field({
  label,
  children,
  className,
}: {
  label: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('min-w-0 space-y-2', className)}>
      <Label>{label}</Label>
      {children}
    </div>
  )
}

function EstimateRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">{value}</span>
    </div>
  )
}
