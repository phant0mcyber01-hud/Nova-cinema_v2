import { useEffect, useState } from 'react'

import { getPublicSettings } from '../api'

/**
 * The administrator's phone and Telegram handle.
 *
 * Payment happens by hand: the viewer files a request and the administrator
 * calls back with the details. Those contacts are therefore shown on the
 * booking screens — and they come from the admin panel, because a number
 * hardcoded in the bundle cannot be changed without a redeploy.
 */
export function useAdminContacts() {
  const [contacts, setContacts] = useState({ phone: '', telegram: '' })

  useEffect(() => {
    let active = true
    void getPublicSettings()
      .then(settings => {
        if (!active) return
        setContacts({
          phone: settings.admin_phone || settings.phone || '',
          telegram: (settings.admin_telegram || '').replace(/^@/, ''),
        })
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [])

  return contacts
}
