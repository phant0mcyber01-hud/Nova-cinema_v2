import WebApp from '@twa-dev/sdk'

export const haptic = {
  tap: () => WebApp.HapticFeedback.impactOccurred('light'),
  select: () => WebApp.HapticFeedback.selectionChanged(),
  success: () => WebApp.HapticFeedback.notificationOccurred('success'),
  error: () => WebApp.HapticFeedback.notificationOccurred('error'),
}
