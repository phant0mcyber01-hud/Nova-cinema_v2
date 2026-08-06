import WebApp from '@twa-dev/sdk'
import { useI18n, type Language } from './i18n'

const languages: { value: Language; label: string }[] = [
  { value: 'ru', label: 'RU' },
  { value: 'uz', label: 'UZ' },
]

export default function LanguageSwitcher() {
  const { language, setLanguage } = useI18n()

  const choose = (nextLanguage: Language) => {
    if (nextLanguage === language) return
    WebApp.HapticFeedback.selectionChanged()
    setLanguage(nextLanguage)
  }

  return (
    <div className={`language-switch ${language}`} aria-label="Language">
      <span className="language-thumb" aria-hidden="true" />
      {languages.map(item => (
        <button
          className={language === item.value ? 'active' : ''}
          type="button"
          aria-pressed={language === item.value}
          onClick={() => choose(item.value)}
          key={item.value}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
