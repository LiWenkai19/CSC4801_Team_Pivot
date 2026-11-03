import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

/** 未认证时转登录页，资料未完成时仅放行当前角色的资料页。 */
function RequireAuth() {
    const auth = useAuth();
    const { currentUser, loading, getAuthDestination } = auth;
    const { pathname } = useLocation();

    // 恢复会话尚未结束时先等待，避免误把已登录用户跳转到登录页。
    if (loading) {
        return <div>Loading...</div>;
    };

    // 没有当前用户就跳转登录；资料不完整时只允许进入对应角色的补填页。
    if (!currentUser) {
        return <Navigate to="/login" replace />;
    }
    const destination = getAuthDestination(currentUser);
    if (!currentUser.profile_completed && pathname !== destination) {
        return <Navigate to={destination} replace />;
    }
    // Outlet 是嵌套路由的占位位置；通过检查后才显示里面的页面。
    return <Outlet/>;
}

export default RequireAuth;
