import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import './candidate.css'

/** 统一候选人导航，服务端仍对每个接口检查角色和对象权限。 */
function CandidateLayout() {
    const { currentUser } = useAuth()
    if (currentUser?.role !== 'candidate') return <main><p role="alert">仅候选人可访问此页面。</p><Link to="/navpage">返回主页</Link></main>
    return <main className="candidate-page">
        <nav aria-label="候选人导航">
            <Link to="/navpage">返回主页</Link>
            <NavLink to="/candidate/jobs">职位推荐</NavLink>
            <NavLink to="/candidate/applications">我的申请</NavLink>
            <NavLink to="/candidate/profile">我的资料</NavLink>
        </nav>
        <Outlet />
    </main>
}

export default CandidateLayout
