import { useEffect, useState } from 'react'

export function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false,
  )

  useEffect(() => {
    const mq = window.matchMedia(query)
    const handler = () => setMatches(mq.matches)
    handler()
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [query])

  return matches
}

export function useSimulatedLoading(ms = 900) {
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const t = window.setTimeout(() => setLoading(false), ms)
    return () => window.clearTimeout(t)
  }, [ms])

  const refresh = () => {
    setLoading(true)
    window.setTimeout(() => setLoading(false), ms)
  }

  return { loading, refresh, setLoading }
}
