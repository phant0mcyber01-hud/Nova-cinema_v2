import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

import BottomNav from './BottomNav'
import LanguageSwitcher from './LanguageSwitcher'

/** Common page frame: logo, language switcher and the bottom tab bar. */
export default function Shell({ children }: { children: ReactNode }) {
  return (
    <main className="app">
      <header className="topbar">
        <Link className="logo" to="/">
          <img src="/nova-logo.jpg" alt="Nova Cinema" />
          <span>NOVA <i>CINEMA</i></span>
        </Link>
        <div className="header-actions">
          <LanguageSwitcher />
        </div>
      </header>
      {children}
      <BottomNav />
    </main>
  )
}
