import { useEffect } from 'react'

/**
 * Locks background page scroll while a full-screen modal is open.
 *
 * Without this, Telegram's in-app WebView keeps the page behind the modal
 * scrollable too. A touch that starts on the modal's own scroll area can
 * still bubble into the page's rubber-band/overscroll handling, which snaps
 * the modal's scroll position back to the top mid-gesture -- the "прокрутка
 * лагает / отбрасывается" symptom. Locking `body` with `position:fixed`
 * while the modal is mounted removes that second scroll container so only
 * the modal's own `overflow-y:auto` section can move.
 */
export function useBodyScrollLock(active: boolean) {
  useEffect(() => {
    if (!active) return undefined
    const { body } = document
    const scrollY = window.scrollY
    const previous = {
      position: body.style.position,
      top: body.style.top,
      left: body.style.left,
      right: body.style.right,
      width: body.style.width,
    }
    body.style.position = 'fixed'
    body.style.top = `-${scrollY}px`
    body.style.left = '0'
    body.style.right = '0'
    body.style.width = '100%'
    return () => {
      body.style.position = previous.position
      body.style.top = previous.top
      body.style.left = previous.left
      body.style.right = previous.right
      body.style.width = previous.width
      window.scrollTo(0, scrollY)
    }
  }, [active])
}
