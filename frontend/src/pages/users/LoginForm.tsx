import React from 'react';  // 使用 React 18.2.0
import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext'
import { useNavigate } from 'react-router-dom';
import Brand from '../../components/Brand';
/** 登录成功后直接进入资料完成状态对应的页面。 */
function LoginForm() {  
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [rememberMe, setRememberMe] = useState(false);
    const [error, setError] = useState('');
    const { login, loading } = useAuth();
    const navigate = useNavigate();  // 使用 useNavigate 来导航到其他页面

    /** 提交登录凭据，按认证响应选择目标地址，失败时保留输入。 */
    async function handleLogin(e: React.SubmitEvent<HTMLFormElement>) {
            e.preventDefault();
            if (loading) return;
            setError('');
            try {
                const destination = await login(email, password, rememberMe);
                navigate(destination, { replace: true });
            } catch (error) {
                setError(error instanceof Error ? error.message : '登录失败')
            }
        }

    function handleRegister() {
        navigate('/register');  // 导航到注册页面
    }
    return (
        <section className="auth-panel" aria-labelledby="login-title">
            <header className="auth-brand"><Brand showDescription /></header>
            <div className="auth-content">
                <h1 id="login-title">登录</h1>
                <form onSubmit={handleLogin}>
                    <div className="field">
                        <label htmlFor="login-email">邮箱</label>
                        <input
                            id="login-email"
                            type="email"
                            autoComplete="username"
                            placeholder="输入邮箱"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                        />
                    </div>
                    <div className="field">
                        <label htmlFor="login-password">密码</label>
                        <input
                            id="login-password"
                            type="password"
                            autoComplete="current-password"
                            placeholder="输入密码"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="remember-label">
                            <input
                                type="checkbox"
                                checked={rememberMe}
                                onChange={event => setRememberMe(event.target.checked)}
                                disabled={loading}
                                aria-describedby="remember-login-hint"
                            />
                            记住我
                        </label>
                        <p id="remember-login-hint" className="remember-hint">关闭浏览器后仍保持登录</p>
                    </div>
                    {error && <p className="feedback" role="alert">{error}</p>}
                    <button type="submit" disabled={loading}>
                        {loading ? '登录中...' : '登录'}
                    </button>
                </form>
                <p className="auth-switch">还没有账户？ <button className="button-quiet" onClick={handleRegister} disabled={loading}>注册</button></p>
            </div>
        </section>
    )
}

export default LoginForm;
