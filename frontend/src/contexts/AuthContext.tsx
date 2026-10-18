import { createContext, useState ,useEffect, useContext } from 'react';
import type { AuthResponse, Role, UserPublic as CurrentUser } from '../types';
import { createUser as apiRegister, getCurrentUser, login as apiLogin, logout as apiLogout } from '../api/common_api';

type AuthDestination = '/navpage' | '/candidate/details' | '/employer/details';

/** 根据资料完成状态与角色统一选择认证后的目标页面。 */
function getAuthDestination(user: CurrentUser): AuthDestination {
    if (user.profile_completed) return '/navpage';
    return user.role === 'candidate' ? '/candidate/details' : '/employer/details';
}

type AuthContextValue = {
    currentUser: CurrentUser | null;
    login: (email: string, password: string) => Promise<AuthDestination>;
    register: (email: string, password: string, role: Role) => Promise<AuthDestination>;
    getAuthDestination: (user: CurrentUser) => AuthDestination;
    logout: () => Promise<void>;
    refreshCurrentUser: () => Promise<CurrentUser>;
    loading: boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

/** 维护共享登录态，统一注册、登录后的目标地址及资料状态刷新。 */
export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
    const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
    const [loading, setLoading] = useState(true);


    useEffect(() => {
        getCurrentUser().then((user) => {
            setCurrentUser(user);
        }).catch(() => {
            apiLogout();
        }).finally(() => {
            setLoading(false);
        });
    }, []);


    /** 使用认证响应更新登录态，避免额外查询账户和读取旧状态。 */
    const finishAuthentication = (response: AuthResponse): AuthDestination => {
        setCurrentUser(response.user);
        return getAuthDestination(response.user);
    };

    /** 验证登录凭据，并直接返回后端账户状态对应的目标地址。 */
    const login = async (email: string, password: string): Promise<AuthDestination> => {
        setLoading(true);
        try{
            const response = await apiLogin(email, password);
            return finishAuthentication(response);
        } catch(error) {
            apiLogout();
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
            apiLogout();
            setCurrentUser(null);
            throw error;
        } finally {
            setLoading(false);
        }
    };

    const logout = async () => {
        await apiLogout();
        setCurrentUser(null);
    };

    /** 刷新账户信息而不触发全局加载，保留当前页面的表单状态。 */
    const refreshCurrentUser = async () => {
        const user = await getCurrentUser();
        setCurrentUser(user);
        return user;
    };

    return (
        <AuthContext.Provider value={{ currentUser, loading, login, register, logout, refreshCurrentUser, getAuthDestination }}>
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

