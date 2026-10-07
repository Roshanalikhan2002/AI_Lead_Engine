import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ExternalLink, MoreHorizontal, Eye, Pencil, ListPlus, Send, Download, Trash2 } from 'lucide-react'
import type { Lead } from '@/types'
import { initials } from '@/lib/utils'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { LeadScore } from '@/components/shared/LeadScore'
import { EmailStatusBadge, OpportunityBadge, OutreachStatusBadge } from '@/components/shared/StatusBadge'
import { useToast } from '@/components/shared/Toast'
import { softTransition } from '@/lib/motion'

interface LeadTableProps {
  leads: Lead[]
  selected: string[]
  onSelect: (ids: string[]) => void
}

export function LeadTable({ leads, selected, onSelect }: LeadTableProps) {
  const { toast } = useToast()
  const allSelected = leads.length > 0 && leads.every((l) => selected.includes(l.id))

  const toggleAll = () => {
    onSelect(
      allSelected
        ? selected.filter((id) => !leads.some((l) => l.id === id))
        : [...new Set([...selected, ...leads.map((l) => l.id)])],
    )
  }

  const toggleOne = (id: string) => {
    onSelect(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])
  }

  return (
    <div className="hidden overflow-hidden rounded-xl border border-border bg-card md:block">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1080px] text-left text-sm">
          <thead className="sticky top-0 z-10 border-b border-border bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground backdrop-blur">
            <tr>
              <th className="w-10 px-4 py-3">
                <Checkbox checked={allSelected} onCheckedChange={toggleAll} aria-label="Select all leads" />
              </th>
              <th className="px-4 py-3 font-medium">Company</th>
              <th className="px-4 py-3 font-medium">Industry</th>
              <th className="px-4 py-3 font-medium">Location</th>
              <th className="px-4 py-3 font-medium">Website</th>
              <th className="px-4 py-3 font-medium">Analysis</th>
              <th className="px-4 py-3 font-medium">Contacts</th>
              <th className="px-4 py-3 font-medium">AI Score</th>
              <th className="px-4 py-3 font-medium">Priority</th>
              <th className="px-4 py-3 font-medium">Service</th>
              <th className="px-4 py-3 font-medium">Rating</th>
              <th className="px-4 py-3 font-medium">Opportunity</th>
              <th className="px-4 py-3 font-medium">Score</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {leads.map((lead) => (
              <tr
                key={lead.id}
                className="group transition-colors hover:bg-muted/40 data-[selected=true]:bg-primary/5"
                data-selected={selected.includes(lead.id)}
              >
                <td className="px-4 py-3">
                  <Checkbox
                    checked={selected.includes(lead.id)}
                    onCheckedChange={() => toggleOne(lead.id)}
                    aria-label={`Select ${lead.company}`}
                  />
                </td>
                <td className="px-4 py-3">
                  <Link to={`/leads/${lead.id}`} className="flex items-center gap-3 hover:opacity-90">
                    <Avatar className="h-9 w-9">
                      <AvatarFallback className="bg-primary/10 text-xs text-primary">
                        {initials(lead.company)}
                      </AvatarFallback>
                    </Avatar>
                    <span className="font-medium">{lead.company}</span>
                  </Link>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{lead.industry}</td>
                <td className="px-4 py-3 text-muted-foreground">
                  {lead.city}, {lead.country}
                </td>
                <td className="px-4 py-3">
                  {lead.website ? (
                    <span className="inline-flex max-w-[160px] items-center gap-1 truncate text-primary">
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-muted text-[10px] font-bold text-foreground">
                        {lead.website[0]?.toUpperCase()}
                      </span>
                      <span className="truncate">{lead.website}</span>
                      <ExternalLink className="h-3 w-3 shrink-0 opacity-60" aria-hidden />
                    </span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <AnalysisStatusLabel status={lead.websiteAnalysisStatus} />
                </td>
                <td className="px-4 py-3">
                  <ContactStatusLabel
                    status={lead.contactDiscoveryStatus}
                    count={lead.contactEmailCount}
                    verified={lead.contactsVerifiedCount}
                    unknown={lead.contactsUnknownCount}
                    invalid={lead.contactsInvalidCount}
                  />
                </td>
                <td className="px-4 py-3">
                  {lead.leadScore != null ? (
                    <LeadScore score={lead.leadScore} size="sm" />
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs font-medium uppercase text-muted-foreground">
                    {lead.priority ?? '—'}
                  </span>
                </td>
                <td className="px-4 py-3 capitalize text-muted-foreground">
                  {lead.primaryService ? lead.primaryService.replaceAll('_', ' ') : '—'}
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <span className="tabular-nums">{lead.rating.toFixed(1)}</span>
                  <span className="ml-1 text-xs text-muted-foreground">({lead.reviews})</span>
                </td>
                <td className="px-4 py-3">
                  <OpportunityBadge opportunity={lead.opportunity} />
                </td>
                <td className="px-4 py-3">
                  <LeadScore score={lead.score} size="sm" />
                </td>
                <td className="px-4 py-3">
                  <EmailStatusBadge status={lead.emailStatus} />
                </td>
                <td className="px-4 py-3">
                  <OutreachStatusBadge status={lead.outreachStatus} />
                </td>
                <td className="px-4 py-3 text-right">
                  <LeadActions lead={lead} onAction={(msg) => toast({ title: msg, type: 'success' })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function LeadActions({ lead, onAction }: { lead: Lead; onAction: (msg: string) => void }) {
  const navigate = useNavigate()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${lead.company}`}>
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => navigate(`/leads/${lead.id}`)}>
          <Eye /> View Lead
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onAction('Edit mode opened (demo)')}>
          <Pencil /> Edit
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onAction('Added to list (demo)')}>
          <ListPlus /> Add to List
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onAction('Outreach started (demo)')}>
          <Send /> Start Outreach
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onAction('Exported (demo)')}>
          <Download /> Export
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => onAction('Deleted (demo)')}>
          <Trash2 /> Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function LeadCard({
  lead,
  selected,
  onSelect,
}: {
  lead: Lead
  selected: boolean
  onSelect: () => void
}) {
  const { toast } = useToast()
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={softTransition}
      className="rounded-xl border border-border bg-card p-4 shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="flex items-start gap-3">
        <Checkbox checked={selected} onCheckedChange={onSelect} className="mt-1" aria-label={`Select ${lead.company}`} />
        <Link to={`/leads/${lead.id}`} className="flex min-w-0 flex-1 items-center gap-3">
          <Avatar className="h-11 w-11">
            <AvatarFallback className="bg-primary/10 text-primary">{initials(lead.company)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <p className="truncate font-medium">{lead.company}</p>
            <p className="truncate text-xs text-muted-foreground">
              {lead.industry} · {lead.city}, {lead.country}
            </p>
          </div>
        </Link>
        <LeadActions lead={lead} onAction={(msg) => toast({ title: msg, type: 'success' })} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <LeadScore score={lead.score} size="sm" />
        <OpportunityBadge opportunity={lead.opportunity} />
        <AnalysisStatusLabel status={lead.websiteAnalysisStatus} />
        <ContactStatusLabel
          status={lead.contactDiscoveryStatus}
          count={lead.contactEmailCount}
          verified={lead.contactsVerifiedCount}
          unknown={lead.contactsUnknownCount}
          invalid={lead.contactsInvalidCount}
        />
        {lead.priority ? (
          <span className="inline-flex rounded-md border border-border bg-muted/40 px-2 py-0.5 text-xs font-medium uppercase text-muted-foreground">
            {lead.priority}
          </span>
        ) : null}
        <OutreachStatusBadge status={lead.outreachStatus} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
        <span>
          AI score: {lead.leadScore != null ? lead.leadScore : '—'}
        </span>
        <span className="truncate text-right capitalize">
          {lead.primaryService ? lead.primaryService.replaceAll('_', ' ') : lead.website ?? 'No website'}
        </span>
      </div>
    </motion.div>
  )
}

function AnalysisStatusLabel({ status }: { status?: string }) {
  const label =
    status === 'completed'
      ? 'Analyzed'
      : status === 'running' || status === 'pending'
        ? 'Analyzing'
        : status === 'failed' || status === 'blocked'
          ? 'Failed'
          : status === 'not_available'
            ? 'No Website'
            : 'Not Analyzed'
  return (
    <span className="inline-flex rounded-md border border-border bg-muted/40 px-2 py-0.5 text-xs font-medium text-muted-foreground">
      {label}
    </span>
  )
}

function ContactStatusLabel({
  status,
  count,
  verified,
  unknown,
  invalid,
}: {
  status?: string
  count?: number
  verified?: number
  unknown?: number
  invalid?: number
}) {
  if (status === 'completed' && (count ?? 0) > 0) {
    return (
      <div className="space-y-0.5 text-xs text-muted-foreground">
        <p>
          Emails: <span className="font-medium text-foreground">{count}</span>
        </p>
        <p>
          Verified: <span className="font-medium text-foreground">{verified ?? 0}</span>
          {' · '}
          Unknown: <span className="font-medium text-foreground">{unknown ?? 0}</span>
          {' · '}
          Invalid: <span className="font-medium text-foreground">{invalid ?? 0}</span>
        </p>
      </div>
    )
  }
  const label =
    status === 'completed'
      ? 'Discovered'
      : status === 'no_public_email'
        ? 'No Public Email'
        : status === 'failed'
          ? 'Failed'
          : status === 'running' || status === 'pending'
            ? 'Discovering'
            : 'Not Discovered'
  return (
    <span className="inline-flex rounded-md border border-border bg-muted/40 px-2 py-0.5 text-xs font-medium text-muted-foreground">
      {label}
    </span>
  )
}
