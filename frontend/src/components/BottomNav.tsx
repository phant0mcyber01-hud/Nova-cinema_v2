import { Link, useLocation } from 'react-router-dom'

import { isAdmin } from '../api'
import { useI18n, type TranslationKey } from '../i18n'
import { haptic } from '../lib/haptic'

type NavItem = { to: string; icon: string; labelKey: TranslationKey; match: (path: string) => boolean }

const items: NavItem[] = [
  { to: '/', icon: '⌂', labelKey: 'navPoster', match: path => path === '/' || path.startsWith('/movies') || path.startsWith('/booking') },
  { to: '/profile/bookings', icon: '▣', labelKey: 'navTickets', match: path => path.startsWith('/profile/bookings') },
  { to: '/about', icon: 'ⓘ', labelKey: 'navAbout', match: path => path.startsWith('/about') },
  { to: '/profile', icon: '☺', labelKey: 'profile', match: path => path === '/profile' || path.startsWith('/profile/favorites') || path.startsWith('/profile/notifications') },
]

/** Mobile-first tab bar; the layout already reserves room for it at the bottom. */
export default function BottomNav() {
  const { t } = useI18n()
  const { pathname } = useLocation()
  const links = isAdmin()
    ? [...items, { to: '/admin', icon: '⚙', labelKey: 'admin' as TranslationKey, match: (path: string) => path.startsWith('/admin') }]
    : items

  return (
    <nav className="bottom-nav" aria-label="Nova Cinema">
      {links.map(item => (
        <Link
          key={item.to}
          to={item.to}
          onClick={haptic.tap}
          className={item.match(pathname) ? 'active' : ''}
          aria-current={item.match(pathname) ? 'page' : undefined}
        >
          <b aria-hidden="true">{item.icon}</b>
          <small>{t(item.labelKey)}</small>
        </Link>
      ))}
    </nav>
  )
}
