import React from 'react';  // 使用 React 18.2.0
import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext'
import { useNavigate } from 'react-router-dom';
import Brand from '../../components/Brand';
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback } from '../../i18n/apiFeedback'
/** 登录成功后直接进入资料完成状态对应的页面。 */
function LoginForm() {  
    const { t } = useLanguage()
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [rememberMe, setRememberMe] = useState(false);
    const [error, setError] = useState<MessageKey | ''>('');
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
                setError(apiFeedback(error, 'auth.loginFailed'))
            }
        }

    function handleRegister() {
        navigate('/register');  // 导航到注册页面
    }
    return (
        <section className="auth-panel" aria-labelledby="login-title">
            <header className="auth-brand"><Brand showDescription /></header>
            <div className="auth-content">
                <h1 id="login-title">{t('auth.signIn')}</h1>
                <form onSubmit={handleLogin}>
                    <div className="field">
                        <label htmlFor="login-email">{t('auth.email')}</label>
                        <input
                            id="login-email"
                            type="email"
                            autoComplete="username"
                            placeholder={t('auth.emailPlaceholder')}
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                        />
                    </div>
                    <div className="field">
                        <label htmlFor="login-password">{t('auth.password')}</label>
                        <input
                            id="login-password"
                            type="password"
                            autoComplete="current-password"
                            placeholder={t('auth.passwordPlaceholder')}
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
                            {t('auth.remember')}
                        </label>
                        <p id="remember-login-hint" className="remember-hint">{t('auth.rememberHint')}</p>
                    </div>
                    {error && <p className="feedback" role="alert">{t(error)}</p>}
                    <button type="submit" disabled={loading}>
                        {loading ? t('auth.signingIn') : t('auth.signIn')}
                    </button>
                </form>
                <p className="auth-switch">{t('auth.noAccount')} <button className="button-quiet" onClick={handleRegister} disabled={loading}>{t('auth.signUp')}</button></p>
            </div>
        </section>
    )
}

export default LoginForm;
