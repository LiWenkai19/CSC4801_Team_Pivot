import { createContext, useState, useEffect, useContext, useRef } from "react";
import type { ReactNode } from "react";
import type { AuthResponse, Role, UserPublic as CurrentUser } from "../types";
import {
  createUser as apiRegister,
  getCurrentUser,
  login as apiLogin,
} from "../api/common_api";

type AuthDestination = "/navpage" | "/candidate/details" | "/employer/details";

/** 完成状态只相信后端；资料完成者进入队友原有主页，不另建第二套登录导航。 */
function getAuthDestination(user: CurrentUser): AuthDestination {
  if (user.profile_completed) return "/navpage";
  return user.role === "candidate" ? "/candidate/details" : "/employer/details";
}

type AuthContextValue = {
  currentUser: CurrentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<AuthDestination>;
  register: (
    email: string,
    password: string,
    role: Role,
  ) => Promise<AuthDestination>;
  getAuthDestination: (user: CurrentUser) => AuthDestination;
  logout: () => Promise<void>;
  refreshCurrentUser: () => Promise<CurrentUser>;
};
export const AuthContext = createContext<AuthContextValue | null>(null);

/** 保留新版注册/登录契约，增加会话版本，防止旧请求在注销或换账户后恢复旧身份。 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(() => !!localStorage.getItem("token"));
  const generation = useRef(0);

  function clearSession() {
    generation.current++;
    localStorage.removeItem("token");
    setCurrentUser(null);
    setLoading(false);
  }

  useEffect(() => {
    let active = true;
    const version = generation.current;
    const token = localStorage.getItem("token");
    if (token) {
      getCurrentUser()
        .then((user) => {
          if (active && version === generation.current) setCurrentUser(user);
        })
        .catch(() => {
          if (active && version === generation.current) clearSession();
        })
        .finally(() => {
          if (active && version === generation.current) setLoading(false);
        });
    }
    // API 的 401 与其他标签页换账户，都必须清除当前页旧的私有资料。
    function storageChanged(event: StorageEvent) {
      if (event.key === "token" || event.key === null) clearSession();
    }
    window.addEventListener("auth-expired", clearSession);
    window.addEventListener("storage", storageChanged);
    return () => {
      active = false;
      window.removeEventListener("auth-expired", clearSession);
      window.removeEventListener("storage", storageChanged);
    };
  }, []);

  /** 只接收本次仍有效的认证结果；不额外调用 /me，保留队友的单请求认证流程。 */
  async function authenticate(
    operation: () => Promise<AuthResponse>,
  ): Promise<AuthDestination> {
    const version = ++generation.current;
    setLoading(true);
    setCurrentUser(null);
    try {
      const response = await operation();
      if (version !== generation.current)
        throw new Error("登录状态已变化，请重新登录。");
      localStorage.setItem("token", response.access_token);
      setCurrentUser(response.user);
      return getAuthDestination(response.user);
    } catch (error) {
      if (version === generation.current) clearSession();
      throw error;
    } finally {
      if (version === generation.current) setLoading(false);
    }
  }

  async function login(email: string, password: string) {
    // API 先不保存 Token，由当前仍有效的 authenticate 统一保存，避免迟到请求污染新会话。
    return authenticate(() => apiLogin(email, password, false, false));
  }
  async function register(email: string, password: string, role: Role) {
    return authenticate(() => apiRegister(email, password, role, false));
  }
  async function logout() {
    clearSession();
  }

  /** 刷新完成状态不触发全局 loading，避免销毁仍需保留输入的表单。 */
  async function refreshCurrentUser() {
    const version = generation.current;
    const token = localStorage.getItem("token");
    const user = await getCurrentUser();
    if (
      version !== generation.current ||
      token !== localStorage.getItem("token")
    ) {
      throw new Error("登录状态已变化，请重新登录。");
    }
    setCurrentUser(user);
    return user;
  }

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        loading,
        login,
        register,
        getAuthDestination,
        logout,
        refreshCurrentUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth 必须在 <AuthProvider> 内部使用");
  return auth;
}
