import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'

/** 登录页与工作台使用同一品牌标识；传入 to 时品牌可点击跳转。 */
export default function Brand({ showDescription = false, to }: { showDescription?: boolean; to?: string }) {
    const { t } = useLanguage()
    const content = <>
        <span className="brand-mark" aria-hidden="true" />
        <span>SkillMatch</span>
        {showDescription && <span className="brand-description">{t('common.brandDescription')}</span>}
    </>
    return to
        ? <Link className="brand" to={to}>{content}</Link>
        : <div className="brand">{content}</div>
}
