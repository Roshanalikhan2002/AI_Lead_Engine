import { Suspense, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Sidebar } from './Sidebar'
import { MobileSidebar } from './MobileSidebar'
import { Topbar } from './Topbar'
import { SkeletonDashboard } from '@/components/shared/Skeleton'

function RouteFallback() {
  return (
    <div className="min-w-0" aria-busy="true" aria-live="polite">
      <div className="mb-6 space-y-2">
        <div className="h-8 w-48 max-w-full rounded-md bg-muted shimmer" />
        <div className="h-4 w-72 max-w-full rounded-md bg-muted shimmer" />
      </div>
      <SkeletonDashboard />
    </div>
  )
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  return (
    <div className="flex min-h-dvh min-w-0 overflow-x-hidden bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        Skip to main content
      </a>

      <div className="hidden lg:sticky lg:top-0 lg:flex lg:h-dvh lg:shrink-0">
        <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      </div>

      <MobileSidebar open={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col overflow-x-hidden">
        <Topbar onMenuClick={() => setMobileOpen(true)} />
        <main id="main-content" className="min-w-0 flex-1 overflow-x-hidden">
          <div className="mx-auto w-full max-w-[1440px] px-3 py-5 sm:px-6 sm:py-6 lg:px-8 xl:px-10">
            <Suspense fallback={<RouteFallback />}>
              <AnimatePresence mode="wait">
                <motion.div
                  key={location.pathname}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.18, ease: 'easeOut' }}
                >
                  <Outlet />
                </motion.div>
              </AnimatePresence>
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  )
}
