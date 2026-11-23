import { createContext, useContext } from 'react'
import type { MessageKey } from './zh-CN'

export type Locale = 'zh-CN' | 'en-US'
export type MessageValues = Record<string, string | number>
export type Message = MessageKey | { key: MessageKey; values: MessageValues }

type Language = {
    locale: Locale
    setLocale: (locale: Locale) => void
    t: (message: Message, values?: MessageValues) => string
}

export const LanguageContext = createContext<Language | null>(null)

export function useLanguage() {
    const language = useContext(LanguageContext)
    if (!language) throw new Error('LanguageProvider is missing')
    return language
}
