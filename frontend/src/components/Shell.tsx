import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

import { useI18n } from '../i18n'
import LanguageSwitcher from './LanguageSwitcher'

/** Common page frame: logo, language switcher and the profile shortcut. */
export default function Shell({ children }: { children: ReactNode }) {
  const { t } = useI18n()

  return (
    <main className="app">
      <header className="topbar">
        <Link className="logo" to="/">
          <img src="/nova-logo.jpg" alt="Nova Cinema" />
          <span>NOVA <i>CINEMA</i></span>
        </Link>
        <div className="header-actions">
          <LanguageSwitcher />
          <Link className="admin-ghost" to="/profile">{t('profile')}</Link>
        </div>
      </header>
      {children}
    </main>
  )
}
