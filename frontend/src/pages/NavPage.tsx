import { useAuth } from '../contexts/AuthContext'
import { Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'

/** 登录后的角色入口；候选人工作流按规划保留提示。 */
function NavPage() {
    const { currentUser, logout } = useAuth()
    const navigate = useNavigate()
    const [notice, setNotice] = useState('')
    
    return (
        <div>
            <h1>欢迎，{currentUser?.email}！</h1>
            {currentUser?.role === 'employer' && <nav aria-label="雇主入口">
                <p><button type="button" onClick={() => navigate('/employer/jobs')}>雇主工作流</button></p>
                <p><Link to="/employer/company">公司资料</Link></p>
            </nav>}
            {currentUser?.role === 'candidate' && <>
                <button type="button" onClick={() => setNotice('候选人工作流尚未实现')}>候选人工作流</button>
                {notice && <p role="status">{notice}</p>}
            </>}
            <button onClick={logout}>注销</button>
        </div>
    )
}

export default NavPage
