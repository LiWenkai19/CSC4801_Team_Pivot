import { useAuth } from '../contexts/AuthContext'
import { Link } from 'react-router-dom'
import React from 'react'

function NavPage() {
    const { currentUser, logout } = useAuth()
    
    return (
        <div>
            <h1>欢迎，{currentUser?.email}！</h1>
            <button onClick={logout}>注销</button>
        </div>
    )
}

export default NavPage