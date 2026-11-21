import React from 'react';
import { useState } from 'react';
import type { Role } from "../../types"
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import Brand from '../../components/Brand';
/** 注册账号并直接进入认证结果指定的角色资料页。 */
function RegisterPage() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState<Role>('candidate'); // 默认为候选人
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const { register, loading } = useAuth();
    const navigate = useNavigate();

    /** 校验确认密码，注册成功后直接跳转，失败时保留输入。 */
    const handleSubmit = async (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (loading) return;
        setError('');

        if (password !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }

        try {
            const destination = await register(email, password, role);
            navigate(destination, { replace: true });
        } catch (error) {
            console.error('Error creating user:', error);
            setError(error instanceof Error ? error.message : 'Failed to create user');
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
                    <h1 id="register-title">注册</h1>
                    <form onSubmit={handleSubmit}>
                        <div className="field">
                            <label htmlFor="register-email">邮箱</label>
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
                            <label htmlFor="register-password">密码</label>
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
                            <label htmlFor="register-confirm">确认密码</label>
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
                            <label htmlFor="role">角色</label>
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
                                <option value="candidate">候选人</option>
                                <option value="employer">雇主</option>
                            </select>
                        </div>
                        {error && <p className="feedback" role="alert">{error}</p>}
                        <button type="submit" disabled={loading}>
                            {loading ? '注册中...' : '注册'}
                        </button>
                    </form>
                    <p className="auth-switch"><button className="button-quiet" onClick={handleBackToLogin} disabled={loading}>返回登录</button></p>
                </div>
            </section>
        </main>
    );
}

export default RegisterPage;
