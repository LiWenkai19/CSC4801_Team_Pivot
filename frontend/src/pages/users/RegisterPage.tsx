import React from 'react';
import { useState } from 'react';
import type { Role } from "../../types"
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
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
        <div style={{ maxWidth: 360, margin: '80px auto', fontFamily: 'sans-serif' }}>
            <h2>注册 SYManage</h2>
            <form onSubmit={handleSubmit}>
                <div style={{ marginBottom: 12 }}>
                    <label>邮箱</label>
                    <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        style={{ display: 'block', width: '100%' }}
                        required
                        disabled={loading}
                    />
                </div>
                <div style={{ marginBottom: 12 }}>
                    <label>密码</label>
                    <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        style={{ display: 'block', width: '100%' }}
                        required
                        disabled={loading}
                    />
                </div>
                <div style={{ marginBottom: 12 }}>
                    <label>确认密码</label>
                    <input
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        style={{ display: 'block', width: '100%' }}
                        required
                        disabled={loading}
                    />
                </div>
                <div style={{ marginBottom: 12 }}>
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
                        style={{ display: 'block', width: '100%' }}
                        required
                        disabled={loading}
                    >
                        <option value="candidate">候选人</option>
                        <option value="employer">雇主</option>
                    </select>
                </div>
                <button type="submit" disabled={loading}>
                    {loading ? '注册中...' : '注册'}
                </button>
            </form>

            <button onClick={handleBackToLogin} disabled={loading} style={{ marginTop: 8 }}>
                返回登录
            </button>

            {error && <p style={{ color: 'red' }}>{error}</p>}
        </div>
    );
}

export default RegisterPage;
