import clsx from 'clsx'
import { useId } from 'react'

/**
 * WSL Technologies mark, traced from the company logo. The two outer strokes use the current text
 * color (dark on light backgrounds, white on dark ones); the inner chevron keeps the brand blue.
 */
export default function Logo({ className = 'size-9' }: { className?: string }) {
  const gradient = useId()
  return (
    <svg viewBox="-10 -10 1280 843" className={className} aria-hidden>
      <defs>
        <linearGradient id={gradient} x1="0" y1="192" x2="0" y2="823" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#0088ff" />
          <stop offset="1" stopColor="#00b4ff" />
        </linearGradient>
      </defs>
      <path fill="currentColor" d="M0 0H520L601 145L499 321L416 179H305L443 420L341 598Z" />
      <path fill="currentColor" d="M1260 0H740L659 145L761 321L844 179H955L817 420L919 598Z" />
      <path fill={`url(#${gradient})`} d="M630 192L892 645L790 823L630 548L470 823L368 645Z" />
    </svg>
  )
}

/** Mark plus "WSL Technologies" wordmark. */
export function Brand({ className, markClass = 'size-9', subtitle }: { className?: string; markClass?: string; subtitle?: string }) {
  return (
    <span className={clsx('flex items-center gap-2.5', className)}>
      <Logo className={markClass} />
      <span className="leading-none">
        <span className="block text-[19px] font-extrabold tracking-[-0.02em]">
          WSL <span className="font-medium opacity-80">Technologies</span>
        </span>
        {subtitle && <span className="mt-1 block text-[11px] font-medium tracking-wide opacity-60">{subtitle}</span>}
      </span>
    </span>
  )
}
