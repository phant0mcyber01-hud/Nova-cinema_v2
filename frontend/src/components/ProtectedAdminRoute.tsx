import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'

import { getAuthState, waitForAuth, type AuthState } from '../api'
import Admin from '../pages/admin/Admin'
import Shell from './Shell'

/** Server-side checks still gate every admin endpoint; this only hides the UI. */
export default function ProtectedAdminRoute() {
  const [auth, setAuth] = useState<AuthState>(getAuthState)

  useEffect(() => {
    let active = true
    void waitForAuth().finally(() => {
      if (active) setAuth(getAuthState())
    })
    return () => { active = false }
  }, [])

  if (!auth.ready) return <Shell><div className="hall-skeleton" /></Shell>
  if (!auth.authenticated || !auth.isAdmin) return <Navigate to="/" replace />
  return <Admin />
}
