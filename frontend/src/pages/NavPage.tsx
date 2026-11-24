import { useAuth } from '../contexts/AuthContext'
import { Link } from 'react-router-dom'
import Brand from '../components/Brand'
import LanguageSwitcher from '../components/LanguageSwitcher'
import { useLanguage } from '../i18n/LanguageContext'

const workspaceNavigation = {
    employer: {
        label: 'home.employerNav',
        links: [
            { title: 'home.employerWorkflow', description: 'home.employerWorkflowDescription', to: '/employer/jobs' },
            { title: 'company.title', description: 'home.companyDescription', to: '/employer/company' },
            { title: 'slots.title', description: 'home.slotsDescription', to: '/employer/interview-slots' },
        ],
    },
    candidate: {
        label: 'home.candidateNav',
        links: [
            { title: 'home.candidateWorkflow', description: 'home.candidateWorkflowDescription', to: '/candidate/jobs' },
            { title: 'profile.title', description: 'home.profileDescription', to: '/candidate/profile' },
            { title: 'applications.title', description: 'home.applicationsDescription', to: '/candidate/applications' },
        ],
    },
} as const

/** 登录后的角色入口；各角色沿用各自的工作流。 */
function NavPage() {
    const { t } = useLanguage()
    const { currentUser, logout, logoutState } = useAuth()
    const navigation = currentUser && workspaceNavigation[currentUser.role]

    return (
        <main className="work-page home-page">
            <header className="workspace-header">
                <Brand />
                <div className="workspace-header-actions">
                    <LanguageSwitcher />
                    <button type="button" onClick={logout} disabled={logoutState === 'pending'}>{t('auth.signOut')}</button>
                </div>
            </header>
            {logoutState && logoutState !== 'pending' && <p className="feedback" role="alert">{t(logoutState)}</p>}
            <h1>{t('home.title')}</h1>
            <p className="home-email">{currentUser?.email}</p>
            {navigation && <nav className="home-nav" aria-label={t(navigation.label)}>
                {navigation.links.map(({ title, description, to }, index) => (
                    <Link
                        key={to}
                        to={to}
                        className={index === 0 ? 'button button-primary home-nav-link' : 'button home-nav-link'}
                        aria-label={t(title)}
                        aria-describedby={`home-entry-${index}`}
                    >
                        <span className="home-nav-title">{t(title)}</span>
                        <span className="home-nav-description" id={`home-entry-${index}`}>{t(description)}</span>
                    </Link>
                ))}
            </nav>}
        </main>
    )
}

export default NavPage
