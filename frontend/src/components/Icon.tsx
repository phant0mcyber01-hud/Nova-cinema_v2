import type { ComponentType } from 'react'
import {
  Check,
  Camera,
  Film,
  Flame,
  Home,
  Hourglass,
  Info,
  MapPin,
  Music2,
  Pencil,
  Phone,
  Search,
  Send,
  Settings,
  Share2,
  Sparkles,
  Star,
  Ticket,
  UserRound,
  VolumeX,
  type LucideProps,
} from 'lucide-react'

export type IconName =
  | 'check'
  | 'film'
  | 'flame'
  | 'home'
  | 'info'
  | 'instagram'
  | 'map'
  | 'music'
  | 'muted'
  | 'new'
  | 'pencil'
  | 'phone'
  | 'profile'
  | 'search'
  | 'send'
  | 'settings'
  | 'share'
  | 'star'
  | 'ticket'
  | 'timer'

const icons: Record<IconName, ComponentType<LucideProps>> = {
  check: Check,
  film: Film,
  flame: Flame,
  home: Home,
  info: Info,
  instagram: Camera,
  map: MapPin,
  music: Music2,
  muted: VolumeX,
  new: Sparkles,
  pencil: Pencil,
  phone: Phone,
  profile: UserRound,
  search: Search,
  send: Send,
  settings: Settings,
  share: Share2,
  star: Star,
  ticket: Ticket,
  timer: Hourglass,
}

type IconProps = Omit<LucideProps, 'ref'> & { name: IconName }

/** Inline SVG icons render identically without relying on device glyph fonts. */
export default function Icon({ name, className = '', ...props }: IconProps) {
  const Glyph = icons[name]
  return (
    <Glyph
      aria-hidden="true"
      className={`nova-icon ${className}`.trim()}
      focusable="false"
      strokeWidth={2.2}
      {...props}
    />
  )
}
