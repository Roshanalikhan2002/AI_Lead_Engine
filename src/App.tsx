import { lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AppShell } from '@/components/layout/AppShell'
import { ThemeProvider } from '@/hooks/useTheme'
import { ToastProvider } from '@/components/shared/Toast'
import { AuthProvider } from '@/hooks/useAuth'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'

const DashboardPage = lazy(() =>
  import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })),
)
const FindLeadsPage = lazy(() =>
  import('@/pages/FindLeadsPage').then((m) => ({ default: m.FindLeadsPage })),
)
const LeadsPage = lazy(() => import('@/pages/LeadsPage').then((m) => ({ default: m.LeadsPage })))
const LeadDetailPage = lazy(() =>
  import('@/pages/LeadDetailPage').then((m) => ({ default: m.LeadDetailPage })),
)
const CampaignsPage = lazy(() =>
  import('@/pages/CampaignsPage').then((m) => ({ default: m.CampaignsPage })),
)
const CampaignCreatePage = lazy(() =>
  import('@/pages/CampaignCreatePage').then((m) => ({ default: m.CampaignCreatePage })),
)
const CampaignDetailPage = lazy(() =>
  import('@/pages/CampaignDetailPage').then((m) => ({ default: m.CampaignDetailPage })),
)
const EmailTemplatesPage = lazy(() =>
  import('@/pages/EmailTemplatesPage').then((m) => ({ default: m.EmailTemplatesPage })),
)
const RepliesPage = lazy(() => import('@/pages/RepliesPage').then((m) => ({ default: m.RepliesPage })))
const AnalyticsPage = lazy(() =>
  import('@/pages/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })),
)
const MeetingsPage = lazy(() =>
  import('@/pages/MeetingsPage').then((m) => ({ default: m.MeetingsPage })),
)
const PipelinePage = lazy(() =>
  import('@/pages/PipelinePage').then((m) => ({ default: m.PipelinePage })),
)
const PublicBookingPage = lazy(() =>
  import('@/pages/PublicBookingPage').then((m) => ({ default: m.PublicBookingPage })),
)
const LeadListsPage = lazy(() =>
  import('@/pages/LeadListsPage').then((m) => ({ default: m.LeadListsPage })),
)
const LeadSourcesPage = lazy(() =>
  import('@/pages/LeadSourcesPage').then((m) => ({ default: m.LeadSourcesPage })),
)
const SettingsPage = lazy(() =>
  import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })),
)
const PricingPage = lazy(() =>
  import('@/pages/PricingPage').then((m) => ({ default: m.PricingPage })),
)
const LoginPage = lazy(() => import('@/pages/AuthPages').then((m) => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import('@/pages/AuthPages').then((m) => ({ default: m.RegisterPage })))
const ForgotPasswordPage = lazy(() =>
  import('@/pages/AuthPages').then((m) => ({ default: m.ForgotPasswordPage })),
)
const ResetPasswordPage = lazy(() =>
  import('@/pages/AuthPages').then((m) => ({ default: m.ResetPasswordPage })),
)
const InviteAcceptPage = lazy(() =>
  import('@/pages/AuthPages').then((m) => ({ default: m.InviteAcceptPage })),
)

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <TooltipProvider delayDuration={200}>
          <AuthProvider>
            <BrowserRouter>
              <Routes>
                <Route path="book/:token" element={<PublicBookingPage />} />
                <Route path="login" element={<LoginPage />} />
                <Route path="register" element={<RegisterPage />} />
                <Route path="forgot-password" element={<ForgotPasswordPage />} />
                <Route path="reset-password" element={<ResetPasswordPage />} />
                <Route path="invite/:token" element={<InviteAcceptPage />} />
                <Route element={<ProtectedRoute />}>
                  <Route element={<AppShell />}>
                    <Route index element={<DashboardPage />} />
                    <Route path="find-leads" element={<FindLeadsPage />} />
                    <Route path="leads" element={<LeadsPage />} />
                    <Route path="leads/:id" element={<LeadDetailPage />} />
                    <Route path="lists" element={<LeadListsPage />} />
                    <Route path="sources" element={<LeadSourcesPage />} />
                    <Route path="analytics" element={<AnalyticsPage />} />
                    <Route path="campaigns" element={<CampaignsPage />} />
                    <Route path="campaigns/new" element={<CampaignCreatePage />} />
                    <Route path="campaigns/:id" element={<CampaignDetailPage />} />
                    <Route path="templates" element={<EmailTemplatesPage />} />
                    <Route path="replies" element={<RepliesPage />} />
                    <Route path="meetings" element={<MeetingsPage />} />
                    <Route path="pipeline" element={<PipelinePage />} />
                    <Route path="settings" element={<SettingsPage />} />
                    <Route path="pricing" element={<PricingPage />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Route>
                </Route>
              </Routes>
            </BrowserRouter>
          </AuthProvider>
        </TooltipProvider>
      </ToastProvider>
    </ThemeProvider>
  )
}
