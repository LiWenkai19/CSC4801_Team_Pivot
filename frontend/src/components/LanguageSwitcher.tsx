import { useLanguage } from '../i18n/LanguageContext'

/** 用同一个按钮在中英文之间切换，并突出当前语言。 */
export default function LanguageSwitcher() {
    const { locale, setLocale, t } = useLanguage()
    const nextLocale = locale === 'zh-CN' ? 'en-US' : 'zh-CN'

    return <button className="language-switch" type="button" aria-label={t('common.switchLanguage')} onClick={() => setLocale(nextLocale)}>
        <span className="language-switch-mark" aria-hidden="true">
            <span data-active={locale === 'zh-CN'}>CH</span>
            <span data-active={locale === 'en-US'}>EN</span>
        </span>
    </button>
}
