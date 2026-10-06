import { createContext, useState ,useEffect, useContext } from 'react';
import type { CurrentUser } from '../types';
import { getCurrentUser, login as apiLogin, logout as apiLogout } from '../api/common_api';


type AuthContextValue = {
    currentUser: CurrentUser | null;
    login: (email: string, password: string) => Promise<void>;
    logout: () => Promise<void>;
    loading: boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
    const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
    const [loading, setLoading] = useState(true);


    useEffect(() => {
        getCurrentUser().then((user) => {
            setCurrentUser(user);
        }).catch((error) => {
            apiLogout();
        }).finally(() => {
            setLoading(false);
        });
    }, []);


    const login = async (email: string, password: string) => {
        setLoading(true);
        try{
            await apiLogin(email, password);
            const user = await getCurrentUser();
            setCurrentUser(user);
        } catch(error) {
            apiLogout();
            throw error;
        } finally{
            setLoading(false);
        };
    };

    const logout = async () => {
        await apiLogout();
        setCurrentUser(null);
    };

    return (
        <AuthContext.Provider value={{ currentUser, loading , login, logout }}>
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

