import { useLanguage } from '../i18n/LanguageContext'
/** 登录页与工作台使用同一品牌标识。 */
export default function Brand({ showDescription = false }: { showDescription?: boolean }) {
    const { t } = useLanguage()
    return <div className="brand">
        <span className="brand-mark" aria-hidden="true" />
        <span>SkillMatch</span>
        {showDescription && <span className="brand-description">{t('common.brandDescription')}</span>}
    </div>
}
