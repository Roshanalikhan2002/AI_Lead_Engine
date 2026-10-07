import { AnimatePresence, motion } from 'framer-motion'
import { Sidebar } from './Sidebar'

interface MobileSidebarProps {
  open: boolean
  onClose: () => void
}

export function MobileSidebar({ open, onClose }: MobileSidebarProps) {
  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="fixed inset-y-0 left-0 z-50 lg:hidden"
            initial={{ x: -320 }}
            animate={{ x: 0 }}
            exit={{ x: -320 }}
            transition={{ type: 'spring', stiffness: 380, damping: 36 }}
          >
            <Sidebar collapsed={false} onToggle={() => undefined} onNavigate={onClose} mobile />
          </motion.div>
        </>
      ) : null}
    </AnimatePresence>
  )
}
