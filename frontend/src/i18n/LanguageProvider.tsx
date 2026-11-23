import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { LanguageContext } from './LanguageContext'
import type { Locale, Message, MessageValues } from './LanguageContext'
import zhCN from './zh-CN'
import enUS from './en-US'

const storageKey = 'skillmatch.language'
const dictionaries = { 'zh-CN': zhCN, 'en-US': enUS }

function initialLocale(): Locale {
    try {
        return window.localStorage.getItem(storageKey) === 'en-US' ? 'en-US' : 'zh-CN'
    } catch {
        // 浏览器限制存储时，本次页面仍可切换语言。
        return 'zh-CN'
    }
}

/** 语言偏好独立于登录会话，切换时保留当前路由和组件状态。 */
export default function LanguageProvider({ children }: { children: ReactNode }) {
    const [locale, setLocale] = useState<Locale>(initialLocale)

    useEffect(() => {
        document.documentElement.lang = locale
        document.title = dictionaries[locale]['common.pageTitle']
        try {
            window.localStorage.setItem(storageKey, locale)
        } catch {
            // 存储不可用时仍按当前页面状态渲染。
        }
    }, [locale])

    function t(message: Message, values?: MessageValues) {
        const key = typeof message === 'string' ? message : message.key
        const replacements = typeof message === 'string' ? values : message.values
        return dictionaries[locale][key].replace(/\{(\w+)\}/g, (token, name: string) =>
            String(replacements?.[name] ?? token),
        )
    }

    return <LanguageContext.Provider value={{ locale, setLocale, t }}>{children}</LanguageContext.Provider>
}
