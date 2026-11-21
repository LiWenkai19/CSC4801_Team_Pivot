import { useAuth } from '../contexts/AuthContext'
import { Link } from 'react-router-dom'
import Brand from '../components/Brand'

const workspaceNavigation = {
    employer: {
        label: '雇主入口',
        links: [
            { title: '雇主工作流', description: '发布职位，管理申请人', to: '/employer/jobs' },
            { title: '公司资料', description: '更新公司名称和介绍', to: '/employer/company' },
            { title: '面试时段', description: '创建时段，查看预约', to: '/employer/interview-slots' },
        ],
    },
    candidate: {
        label: '候选人入口',
        links: [
            { title: '候选人工作流', description: '按技能匹配分浏览职位', to: '/candidate/jobs' },
            { title: '我的资料', description: '更新个人简历和技能', to: '/candidate/profile' },
            { title: '我的申请', description: '跟进申请和面试预约', to: '/candidate/applications' },
        ],
    },
}

/** 登录后的角色入口；各角色沿用各自的工作流。 */
function NavPage() {
    const { currentUser, logout } = useAuth()
    const navigation = currentUser && workspaceNavigation[currentUser.role]

    return (
        <main className="work-page home-page">
            <header className="workspace-header">
                <Brand />
                <button type="button" onClick={logout}>注销</button>
            </header>
            <h1>招聘工作台</h1>
            <p className="home-email">{currentUser?.email}</p>
            {navigation && <nav className="home-nav" aria-label={navigation.label}>
                {navigation.links.map(({ title, description, to }, index) => (
                    <Link
                        key={to}
                        to={to}
                        className={index === 0 ? 'button button-primary home-nav-link' : 'button home-nav-link'}
                        aria-label={title}
                        aria-describedby={`home-entry-${index}`}
                    >
                        <span className="home-nav-title">{title}</span>
                        <span className="home-nav-description" id={`home-entry-${index}`}>{description}</span>
                    </Link>
                ))}
            </nav>}
        </main>
    )
}

export default NavPage
