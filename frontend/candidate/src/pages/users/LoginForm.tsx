import React from 'react';  // 使用 React 18.2.0
import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext'
import { useNavigate } from 'react-router-dom';
/** 登录成功后直接进入资料完成状态对应的页面。 */
function LoginForm() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const { login, loading } = useAuth();
    const navigate = useNavigate();  // 使用 useNavigate 来导航到其他页面

    /** 提交登录凭据，按认证响应选择目标地址，失败时保留输入。 */
    async function handleLogin(e: React.SubmitEvent<HTMLFormElement>) {
            e.preventDefault();
            if (loading) return;
            setError('');
            try {
                const destination = await login(email, password);
                navigate(destination, { replace: true });
            } catch (error) {
                setError(error instanceof Error ? error.message : '登录失败')
            }
        }

    function handleRegister() {
        navigate('/register');  // 导航到注册页面
    }
    return (
        <div style={{ maxWidth: 360, margin: '80px auto', fontFamily: 'sans-serif' }}>
            <h2>登录 SkillMatch 职聘匹配平台</h2>
            <form onSubmit={handleLogin}>
                <div style={{ marginBottom: 12 }}>
                    <label htmlFor="login-email">邮箱</label>
                    <input
                        id="login-email" type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        style={{ display: 'block', width: '100%' }}
                    />
                </div>
                <div style={{ marginBottom: 12 }}>
                    <label htmlFor="login-password">密码</label>
                    <input
                        id="login-password" type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        style={{ display: 'block', width: '100%' }}
                    />
                </div>
                <button type="submit" disabled={loading}>
                    {loading ? '登录中...' : '登录'}
                </button>
            </form>
            <button onClick={handleRegister} disabled={loading}>注册</button>
            {error && <p style={{ color: 'red' }}>{error}</p>}
        </div>
    )
}

export default LoginForm;
