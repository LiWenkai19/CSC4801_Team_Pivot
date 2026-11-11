import { useAuth } from '../contexts/AuthContext'
import { Link, useNavigate } from 'react-router-dom'

/** 登录后的角色入口；各角色沿用各自的工作流。 */
function NavPage() {
    const { currentUser, logout } = useAuth()
    const navigate = useNavigate()
    
    return (
        <div>
            <h1>欢迎，{currentUser?.email}！</h1>
            {currentUser?.role === 'employer' && <nav aria-label="雇主入口">
                <p><button type="button" onClick={() => navigate('/employer/jobs')}>雇主工作流</button></p>
                <p><Link to="/employer/company">公司资料</Link></p>
            </nav>}
            {currentUser?.role === 'candidate' && <>
                <button type="button" onClick={() => navigate('/candidate/jobs')}>候选人工作流</button>
                <p><Link to="/candidate/profile">我的资料</Link> · <Link to="/candidate/applications">我的申请</Link></p>
            </>}
            <button onClick={logout}>注销</button>
        </div>
    )
}

export default NavPage
