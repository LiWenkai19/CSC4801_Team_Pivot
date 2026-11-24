import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import Brand from '../../components/Brand'
import LanguageSwitcher from '../../components/LanguageSwitcher'
import './candidate.css'
import { useLanguage } from '../../i18n/LanguageContext'

/** 统一候选人导航，服务端仍对每个接口检查角色和对象权限。 */
function CandidateLayout() {
    const { t } = useLanguage()
    const { currentUser } = useAuth()
    if (currentUser?.role !== 'candidate') return <main className="work-page"><p className="feedback" role="alert">{t('auth.candidateOnly')}</p><Link to="/navpage">{t('common.home')}</Link></main>
    return <div className="candidate-layout">
        <aside className="workspace-nav">
            <Brand to="/navpage" />
            <nav aria-label={t('profile.candidateNav')}>
                <NavLink to="/candidate/jobs"><span className="nav-icon nav-icon-jobs" aria-hidden="true" />{t('jobs.recommended')}</NavLink>
                <NavLink to="/candidate/applications"><span className="nav-icon nav-icon-sheet" aria-hidden="true" />{t('applications.title')}</NavLink>
                <NavLink to="/candidate/profile"><span className="nav-icon nav-icon-person" aria-hidden="true" />{t('profile.title')}</NavLink>
                <LanguageSwitcher />
                <Link className="nav-back" to="/navpage"><span aria-hidden="true">‹</span>{t('common.home')}</Link>
            </nav>
        </aside>
        <main className="candidate-page work-page"><Outlet /></main>
    </div>
}

export default CandidateLayout
