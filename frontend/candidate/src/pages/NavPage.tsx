import { useAuth } from '../contexts/AuthContext'
import { Link } from 'react-router-dom'

function NavPage() {
    const { currentUser, logout } = useAuth()

    return (
        <div>
            <h1>欢迎，{currentUser?.email}！</h1>
            {currentUser?.role === 'candidate' && <nav aria-label="候选人导航">
                <Link to="/candidate/profile">我的资料</Link>{' | '}
                <Link to="/candidate/jobs">职位推荐</Link>{' | '}
                <Link to="/candidate/applications">我的申请</Link>
            </nav>}
            <button onClick={logout}>注销</button>
        </div>
    )
}

export default NavPage
