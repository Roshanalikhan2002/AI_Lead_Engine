import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Search,
  Users,
  ListChecks,
  Radar,
  BarChart3,
  Megaphone,
  Mail,
  Inbox,
  CalendarDays,
  Settings,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Kanban,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useAuth } from '@/hooks/useAuth'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const sections = [
  {
    label: 'Overview',
    items: [{ to: '/', label: 'Dashboard', icon: LayoutDashboard }],
  },
  {
    label: 'Lead Generation',
    items: [
      { to: '/find-leads', label: 'Find Leads', icon: Search },
      { to: '/leads', label: 'All Leads', icon: Users },
      { to: '/lists', label: 'Lead Lists', icon: ListChecks },
      { to: '/sources', label: 'Lead Sources', icon: Radar },
    ],
  },
  {
    label: 'Analytics',
    items: [{ to: '/analytics', label: 'Analytics', icon: BarChart3 }],
  },
  {
    label: 'Outreach',
    items: [
      { to: '/campaigns', label: 'Campaigns', icon: Megaphone },
      { to: '/templates', label: 'Email Templates', icon: Mail },
      { to: '/replies', label: 'Replies', icon: Inbox },
    ],
  },
  {
    label: 'Management',
    items: [
      { to: '/meetings', label: 'Meetings', icon: CalendarDays },
      { to: '/pipeline', label: 'Pipeline', icon: Kanban },
      { to: '/pricing', label: 'Pricing', icon: Sparkles },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
  onNavigate?: () => void
  mobile?: boolean
}

export function Sidebar({ collapsed, onToggle, onNavigate, mobile }: SidebarProps) {
  const { user, organization, role, organizations, switchOrg } = useAuth()
  const initials = `${user?.first_name?.[0] || ''}${user?.last_name?.[0] || user?.email?.[0] || '?'}`.toUpperCase()

  return (
    <aside
      className={cn(
        'flex h-full flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground',
        mobile ? 'w-72' : collapsed ? 'w-[72px]' : 'w-64',
      )}
    >
      <div className={cn('flex h-16 items-center gap-3 px-4', collapsed && !mobile && 'justify-center px-2')}>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
          <Sparkles className="h-4 w-4" />
        </div>
        {(!collapsed || mobile) && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight text-foreground">LeadFlow AI</p>
            <p className="truncate text-[11px] text-muted-foreground">Lead Generation Platform</p>
          </div>
        )}
      </div>

      <Separator />

      {(!collapsed || mobile) && organizations.length > 0 && (
        <div className="px-3 pt-3">
          <p className="mb-1 px-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Organization
          </p>
          <Select
            value={organization?.id}
            onValueChange={(id) => {
              if (id && id !== organization?.id) void switchOrg(id)
            }}
          >
            <SelectTrigger className="h-9">
              <SelectValue placeholder="Select organization" />
            </SelectTrigger>
            <SelectContent>
              {organizations.map((org) => (
                <SelectItem key={org.id} value={org.id}>
                  {org.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {sections.map((section) => (
          <div key={section.label} className="mb-5">
            {(!collapsed || mobile) && (
              <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {section.label}
              </p>
            )}
            <ul className="space-y-1">
              {section.items.map((item) => {
                const navClass = ({ isActive }: { isActive: boolean }) =>
                  cn(
                    'group relative flex min-h-10 items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors',
                    collapsed && !mobile && 'justify-center px-0',
                    isActive
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground shadow-sm'
                      : 'text-sidebar-foreground hover:bg-muted/80 hover:text-foreground',
                  )

                const content = (
                  <>
                    <item.icon className="h-4 w-4 shrink-0" aria-hidden />
                    {(!collapsed || mobile) && <span className="truncate">{item.label}</span>}
                  </>
                )

                if (collapsed && !mobile) {
                  return (
                    <li key={item.to}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <NavLink
                            to={item.to}
                            end={item.to === '/'}
                            onClick={onNavigate}
                            className={navClass}
                            aria-label={item.label}
                          >
                            {content}
                          </NavLink>
                        </TooltipTrigger>
                        <TooltipContent side="right">{item.label}</TooltipContent>
                      </Tooltip>
                    </li>
                  )
                }

                return (
                  <li key={item.to}>
                    <NavLink to={item.to} end={item.to === '/'} onClick={onNavigate} className={navClass}>
                      {({ isActive }) => (
                        <>
                          {isActive ? (
                            <span
                              className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-primary"
                              aria-hidden
                            />
                          ) : null}
                          <item.icon className="h-4 w-4 shrink-0" aria-hidden />
                          {(!collapsed || mobile) && <span className="truncate">{item.label}</span>}
                        </>
                      )}
                    </NavLink>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-3">
        {!mobile && (
          <Button
            variant="ghost"
            size={collapsed ? 'icon' : 'sm'}
            className={cn('mb-2 w-full', collapsed ? '' : 'justify-start')}
            onClick={onToggle}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
            {!collapsed && <span>Collapse</span>}
          </Button>
        )}
        <div className={cn('flex items-center gap-3 rounded-lg p-2', collapsed && !mobile && 'justify-center')}>
          <Avatar className="h-9 w-9">
            <AvatarFallback className="bg-primary/15 text-primary">{initials}</AvatarFallback>
          </Avatar>
          {(!collapsed || mobile) && (
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-foreground">
                {user?.first_name || user?.email || 'User'}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {role || 'member'} · {organization?.name || 'Organization'}
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
