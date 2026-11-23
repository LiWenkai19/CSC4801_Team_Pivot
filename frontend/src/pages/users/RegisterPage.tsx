import React from 'react';
import { useState } from 'react';
import type { Role } from "../../types"
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import Brand from '../../components/Brand';
import { useLanguage } from '../../i18n/LanguageContext'
import type { MessageKey } from '../../i18n/zh-CN'
import { apiFeedback } from '../../i18n/apiFeedback'
/** 注册账号并直接进入认证结果指定的角色资料页。 */
function RegisterPage() {
    const { t } = useLanguage()
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState<Role>('candidate'); // 默认为候选人
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState<MessageKey | ''>('');
    const { register, loading } = useAuth();
    const navigate = useNavigate();

    /** 校验确认密码，注册成功后直接跳转，失败时保留输入。 */
    const handleSubmit = async (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (loading) return;
        setError('');

        if (password !== confirmPassword) {
            setError('auth.passwordMismatch');
            return;
        }

        try {
            const destination = await register(email, password, role);
            navigate(destination, { replace: true });
        } catch (error) {
            console.error('Error creating user:', error);
            setError(apiFeedback(error, 'auth.registrationFailed'));
        }
    };

    const handleBackToLogin = () => {
        navigate('/login');
    };

    return (
        <main className="auth-page">
            <section className="auth-panel" aria-labelledby="register-title">
                <header className="auth-brand"><Brand showDescription /></header>
                <div className="auth-content">
                    <h1 id="register-title">{t('auth.signUp')}</h1>
                    <form onSubmit={handleSubmit}>
                        <div className="field">
                            <label htmlFor="register-email">{t('auth.email')}</label>
                            <input
                                id="register-email"
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                autoComplete="username"
                                required
                                disabled={loading}
                            />
                        </div>
                        <div className="field">
                            <label htmlFor="register-password">{t('auth.password')}</label>
                            <input
                                id="register-password"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                autoComplete="new-password"
                                required
                                disabled={loading}
                            />
                        </div>
                        <div className="field">
                            <label htmlFor="register-confirm">{t('auth.confirmPassword')}</label>
                            <input
                                id="register-confirm"
                                type="password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                autoComplete="new-password"
                                required
                                disabled={loading}
                            />
                        </div>
                        <div className="field">
                            <label htmlFor="role">{t('auth.role')}</label>
                            <select
                                id="role"
                                value={role}
                                onChange={(e) => {
                                    const value = e.target.value;
                                    if (value === 'candidate' || value === 'employer') {
                                        setRole(value);
                                    }
                                }}
                                required
                                disabled={loading}
                            >
                                <option value="candidate">{t('auth.candidate')}</option>
                                <option value="employer">{t('auth.employer')}</option>
                            </select>
                        </div>
                        {error && <p className="feedback" role="alert">{t(error)}</p>}
                        <button type="submit" disabled={loading}>
                            {loading ? t('auth.signingUp') : t('auth.signUp')}
                        </button>
                    </form>
                    <p className="auth-switch"><button className="button-quiet" onClick={handleBackToLogin} disabled={loading}>{t('auth.backToLogin')}</button></p>
                </div>
            </section>
        </main>
    );
}

export default RegisterPage;
