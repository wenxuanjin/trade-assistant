type IconProps = { className?: string }

export function LogoMark() {
  return (
    <svg className="logo-mark" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="7" cy="8" r="2.2" />
      <circle cx="16.5" cy="6.5" r="1.6" />
      <circle cx="17.5" cy="15" r="2.2" />
      <circle cx="8" cy="17" r="1.5" />
    </svg>
  )
}

export function IconChat({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 6.5h12a2 2 0 0 1 2 2v6.2a2 2 0 0 1-2 2H11l-4.2 3v-3H6a2 2 0 0 1-2-2V8.5a2 2 0 0 1 2-2Z" />
    </svg>
  )
}

export function IconFolder({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 7.5A2 2 0 0 1 6 5.5h4l1.6 1.8H18a2 2 0 0 1 2 2v8.2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7.5Z" />
    </svg>
  )
}

export function IconLayout({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="4.5" width="16" height="15" rx="2" />
      <path d="M4 9.5h16M10 9.5v10" />
    </svg>
  )
}

export function IconDoc({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 4.5h7l4 4V19a1.5 1.5 0 0 1-1.5 1.5h-9.5A1.5 1.5 0 0 1 5.5 19V6A1.5 1.5 0 0 1 7 4.5Z" />
      <path d="M14 4.8V9h4.2" />
    </svg>
  )
}

export function IconUsers({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="9" cy="9" r="2.4" />
      <circle cx="16" cy="10" r="1.8" />
      <path d="M4.8 17.5c.6-2.2 2.4-3.4 4.2-3.4s3.6 1.2 4.2 3.4" />
      <path d="M14 14.4c1.5.1 2.9 1 3.5 3.1" />
    </svg>
  )
}

export function IconClock({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="7.2" />
      <path d="M12 8.5V12l2.6 1.8" />
    </svg>
  )
}

export function IconSettings({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 4.5v2.2M12 17.3v2.2M4.5 12h2.2M17.3 12h2.2M6.7 6.7l1.6 1.6M15.7 15.7l1.6 1.6M17.3 6.7l-1.6 1.6M8.3 15.7l-1.6 1.6" />
    </svg>
  )
}

export function IconHelp({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="7.2" />
      <path d="M9.6 9.4a2.4 2.4 0 1 1 3.3 2.2c-.7.4-1.1.9-1.1 1.7V14" />
      <circle cx="12" cy="16.6" r=".7" fill="currentColor" stroke="none" />
    </svg>
  )
}

export function IconSun({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 4.5v2M12 17.5v2M4.5 12h2M17.5 12h2M6.8 6.8l1.4 1.4M15.8 15.8l1.4 1.4M17.2 6.8l-1.4 1.4M8.2 15.8l-1.4 1.4" />
    </svg>
  )
}

export function IconMoon({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M15 5.2A7.2 7.2 0 1 0 18.8 15 6 6 0 0 1 15 5.2Z" />
    </svg>
  )
}

export function IconSearch({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="5.5" />
      <path d="M15.5 15.5 19 19" />
    </svg>
  )
}

export function IconPlus({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 6.5v11M6.5 12h11" />
    </svg>
  )
}

export function IconSend({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 12h11M13 7.5 18 12l-5 4.5" />
    </svg>
  )
}

export function IconMenu({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 7.5h14M5 12h14M5 16.5h14" />
    </svg>
  )
}

export function IconCoin({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <ellipse cx="12" cy="8" rx="6" ry="2.6" />
      <path d="M6 8v4.2c0 1.5 2.7 2.7 6 2.7s6-1.2 6-2.7V8" />
      <path d="M6 12.2v3.6c0 1.5 2.7 2.7 6 2.7s6-1.2 6-2.7v-3.6" />
    </svg>
  )
}

export function IconFlow({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 7h8M6 12h12M6 17h7" />
      <circle cx="17" cy="7" r="1.3" fill="currentColor" stroke="none" />
    </svg>
  )
}

export function IconPay({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="6.5" width="16" height="11" rx="2" />
      <path d="M4 10.5h16" />
    </svg>
  )
}
