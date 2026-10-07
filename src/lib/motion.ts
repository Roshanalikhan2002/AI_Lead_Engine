export const fadeUp = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
}

export const staggerContainer = {
  animate: {
    transition: {
      staggerChildren: 0.06,
    },
  },
}

export const staggerItem = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
}

export const softTransition = { duration: 0.28, ease: [0.22, 1, 0.36, 1] as const }
