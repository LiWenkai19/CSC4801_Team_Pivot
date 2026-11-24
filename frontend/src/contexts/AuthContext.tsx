import { createContext, useState, useEffect, useContext, useRef } from 'react';
import type { AuthResponse, Role, UserPublic as CurrentUser } from '../types';
import { ApiError, createUser as apiRegister, getCurrentUser, login as apiLogin, logout as apiLogout } from '../api/common_api';

type AuthDestination = '/navpage' | '/candidate/details' | '/employer/details';
type LogoutError = 'auth.logoutFailed' | 'auth.logoutUnconfirmed';
type LogoutState = 'pending' | LogoutError | null;

/** 根据资料完成状态与角色统一选择认证后的目标页面。 */
function getAuthDestination(user: CurrentUser): AuthDestination {
    if (user.profile_completed) return '/navpage';
    return user.role === 'candidate' ? '/candidate/details' : '/employer/details';
}

/** 发起注销，失败时检查原会话是否仍有效。 */
async function requestLogout(): Promise<LogoutError | null> {
    try {
        await apiLogout();
        return null;
    } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
    }

    try {
        await getCurrentUser();
        return 'auth.logoutFailed';
    } catch (error) {
        return error instanceof ApiError && error.status === 401
            ? null
            : 'auth.logoutUnconfirmed';
    }
}

type AuthContextValue = {
    currentUser: CurrentUser | null;
    login: (email: string, password: string, rememberMe?: boolean) => Promise<AuthDestination>;
    register: (email: string, password: string, role: Role) => Promise<AuthDestination>;
    getAuthDestination: (user: CurrentUser) => AuthDestination;
    logout: () => Promise<void>;
    logoutState: LogoutState;
    refreshCurrentUser: () => Promise<CurrentUser>;
    loading: boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

/** 维护共享登录态，统一注册、登录后的目标地址及资料状态刷新。 */
export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
    const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
    const [loading, setLoading] = useState(true);
    const [logoutState, setLogoutState] = useState<LogoutState>(null);
    const logoutInFlight = useRef(false);


    useEffect(() => {
        // 会话 Cookie 是 HttpOnly 的，前端无法自己判断是否已登录，只能问后端。
        getCurrentUser().then((user) => {
            setCurrentUser(user);
        }).catch(() => {
            // 401 即未登录（没有 Cookie 或会话已过期/被吊销），无需清理任何本地存储。
            setCurrentUser(null);
        }).finally(() => {
            setLoading(false);
        });
    }, []);


    /** 使用认证响应更新登录态，避免额外查询账户和读取旧状态。 */
    const finishAuthentication = (response: AuthResponse): AuthDestination => {
        setCurrentUser(response.user);
        setLogoutState(null);
        return getAuthDestination(response.user);
    };

    /** 验证登录凭据，并直接返回后端账户状态对应的目标地址。 */
    const login = async (email: string, password: string, rememberMe = false): Promise<AuthDestination> => {
        setLoading(true);
        try{
            const response = await apiLogin(email, password, rememberMe);
            return finishAuthentication(response);
        } catch(error) {
            // 登录失败时后端不会建立会话，只需清空前端状态。
            setCurrentUser(null);
            throw error;
        } finally{
            setLoading(false);
        };
    };

    /** 注册后直接建立登录态，返回对应角色的资料页或主页地址。 */
    const register = async (email: string, password: string, role: Role): Promise<AuthDestination> => {
        setLoading(true);
        try {
            const response = await apiRegister(email, password, role);
            return finishAuthentication(response);
        } catch (error) {
            setCurrentUser(null);
            throw error;
        } finally {
            setLoading(false);
        }
    };

    /** 在服务端会话失效后清空登录态，失败时保留当前页面并提供提示。 */
    const logout = async () => {
        if (logoutInFlight.current) return;
        logoutInFlight.current = true;
        setLogoutState('pending');
        try {
            const error = await requestLogout();
            setLogoutState(error);
            if (error === null) setCurrentUser(null);
        } finally {
            logoutInFlight.current = false;
        }
    };

    /** 刷新账户信息而不触发全局加载，保留当前页面的表单状态。 */
    const refreshCurrentUser = async () => {
        const user = await getCurrentUser();
        setCurrentUser(user);
        return user;
    };

    return (
        <AuthContext.Provider value={{ currentUser, loading, login, register, logout, logoutState, refreshCurrentUser, getAuthDestination }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const auth = useContext(AuthContext);
    if (!auth) {
        throw new Error('useAuth 必须在 <AuthProvider> 内部使用');
    }
    return auth;
};

