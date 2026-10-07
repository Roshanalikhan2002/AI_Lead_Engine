import { useMemo, useState } from 'react'
import { Copy, Eye, Save, Send } from 'lucide-react'
import { PageHeader } from '@/components/shared/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { emailTemplates } from '@/data/mock'
import { useToast } from '@/components/shared/Toast'
import { SkeletonChart } from '@/components/shared/Skeleton'
import { useSimulatedLoading } from '@/hooks/useMediaQuery'

const sampleVars = {
  first_name: 'Sarah',
  company_name: 'Bright Smile Dental',
  industry: 'Dental Clinics',
  website_issue: 'the website is slow on mobile and missing online booking',
  recommended_service: 'a website redesign with appointment automation',
}

function fillTemplate(text: string) {
  return text
    .replaceAll('{{first_name}}', sampleVars.first_name)
    .replaceAll('{{company_name}}', sampleVars.company_name)
    .replaceAll('{{industry}}', sampleVars.industry)
    .replaceAll('{{website_issue}}', sampleVars.website_issue)
    .replaceAll('{{recommended_service}}', sampleVars.recommended_service)
}

export function EmailTemplatesPage() {
  const { loading } = useSimulatedLoading(600)
  const { toast } = useToast()
  const [selectedId, setSelectedId] = useState(emailTemplates[0]?.id ?? '')
  const selected = emailTemplates.find((t) => t.id === selectedId) ?? emailTemplates[0]
  const [name, setName] = useState(selected?.name ?? '')
  const [subject, setSubject] = useState(selected?.subject ?? '')
  const [body, setBody] = useState(selected?.body ?? '')

  const previewSubject = useMemo(() => fillTemplate(subject), [subject])
  const previewBody = useMemo(() => fillTemplate(body), [body])

  if (loading) {
    return (
      <div>
        <PageHeader title="Email Templates" description="Loading editor..." />
        <SkeletonChart className="h-[480px]" />
      </div>
    )
  }

  return (
    <div className="min-w-0">
      <PageHeader
        title="Email Templates"
        description="Craft personalized outreach with live AI preview."
        breadcrumbs={[{ label: 'Outreach' }, { label: 'Email Templates' }]}
        actions={
          <>
            <Button variant="outline" onClick={() => toast({ title: 'Template duplicated (demo)', type: 'info' })}>
              <Copy className="h-4 w-4" />
              <span className="hidden sm:inline">Duplicate</span>
            </Button>
            <Button variant="outline" onClick={() => toast({ title: 'Preview opened (demo)', type: 'info' })}>
              <Eye className="h-4 w-4" />
              <span className="hidden sm:inline">Preview</span>
            </Button>
            <Button onClick={() => toast({ title: 'Template saved (demo)', type: 'success' })}>
              <Save className="h-4 w-4" />
              <span className="hidden sm:inline">Save</span>
            </Button>
          </>
        }
      />

      <div className="mb-4">
        <Select
          value={selectedId}
          onValueChange={(id) => {
            const tpl = emailTemplates.find((t) => t.id === id)
            setSelectedId(id)
            if (tpl) {
              setName(tpl.name)
              setSubject(tpl.subject)
              setBody(tpl.body)
            }
          }}
        >
          <SelectTrigger className="w-full max-w-sm">
            <SelectValue placeholder="Select template" />
          </SelectTrigger>
          <SelectContent>
            {emailTemplates.map((t) => (
              <SelectItem key={t.id} value={t.id}>
                {t.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid min-w-0 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Template fields</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Template name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Subject</Label>
              <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Body</Label>
              <Textarea className="min-h-[280px] font-mono text-[13px]" value={body} onChange={(e) => setBody(e.target.value)} />
            </div>
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Variables</p>
              <div className="flex flex-wrap gap-2">
                {Object.keys(sampleVars).map((key) => (
                  <Badge key={key} variant="outline" className="font-mono">
                    {`{{${key}}}`}
                  </Badge>
                ))}
              </div>
            </div>
            <Button variant="secondary" className="w-full" onClick={() => toast({ title: 'Test email queued (demo)', type: 'success' })}>
              <Send className="h-4 w-4" />
              Send Test Email
            </Button>
          </CardContent>
        </Card>

        <Card className="overflow-hidden">
          <CardHeader className="border-b border-border bg-muted/30">
            <div className="flex items-center justify-between gap-3">
              <CardTitle>Live email preview</CardTitle>
              <Badge>AI Personalization</Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="border-b border-border px-5 py-4 text-sm">
              <p className="text-muted-foreground">To: sarah@brightsmiledental.com</p>
              <p className="mt-1 font-medium">{previewSubject}</p>
            </div>
            <div className="whitespace-pre-wrap px-5 py-6 text-sm leading-relaxed">{previewBody}</div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
