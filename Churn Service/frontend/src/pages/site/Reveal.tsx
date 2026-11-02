import clsx from 'clsx'
import type { ReactNode } from 'react'
import { useInView } from '../../lib/motion'

/** Fades its children up the first time they scroll into view; children can key extra motion off .is-visible. */
export default function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const [ref, visible] = useInView<HTMLDivElement>()
  return (
    <div ref={ref} className={clsx('reveal', visible && 'is-visible', className)} style={delay ? { transitionDelay: `${delay}ms` } : undefined}>
      {children}
    </div>
  )
}
