import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import Brand from '../../components/Brand'
import './candidate.css'

/** 统一候选人导航，服务端仍对每个接口检查角色和对象权限。 */
function CandidateLayout() {
    const { currentUser } = useAuth()
    if (currentUser?.role !== 'candidate') return <main className="work-page"><p className="feedback" role="alert">仅候选人可访问此页面。</p><Link to="/navpage">返回主页</Link></main>
    return <div className="candidate-layout">
        <aside className="workspace-nav">
            <Brand />
            <nav aria-label="候选人导航">
                <NavLink to="/candidate/jobs"><span className="nav-icon nav-icon-jobs" aria-hidden="true" />职位推荐</NavLink>
                <NavLink to="/candidate/applications"><span className="nav-icon nav-icon-sheet" aria-hidden="true" />我的申请</NavLink>
                <NavLink to="/candidate/profile"><span className="nav-icon nav-icon-person" aria-hidden="true" />我的资料</NavLink>
                <Link className="nav-back" to="/navpage"><span aria-hidden="true">‹</span>返回主页</Link>
            </nav>
        </aside>
        <main className="candidate-page work-page"><Outlet /></main>
    </div>
}

export default CandidateLayout
