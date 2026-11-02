import { useEffect, useRef, useState } from 'react'

// Shared motion helpers and constants for the marketing pages.

export const DARK = '#0b0d12'

export const reducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Fires once when the element first scrolls into view. */
export function useInView<T extends Element>(rootMargin = '0px 0px -60px 0px') {
  const ref = useRef<T>(null)
  const [inView, setInView] = useState(() => typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    const el = ref.current
    if (!el || inView) return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setInView(true)
        observer.disconnect()
      }
    }, { rootMargin })
    observer.observe(el)
    return () => observer.disconnect()
  }, [inView, rootMargin])
  return [ref, inView] as const
}
