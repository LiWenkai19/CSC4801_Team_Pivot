import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useLanguage } from '../i18n/LanguageContext'

/** 未认证时转登录页，资料未完成时仅放行当前角色的资料页。 */
function RequireAuth() {
    const { t } = useLanguage()
    const auth = useAuth();
    const { currentUser, loading, getAuthDestination } = auth;
    const { pathname } = useLocation();

    if (loading) {
        return <main className="work-page"><p className="feedback" role="status">{t('auth.checking')}</p></main>;
    };

    if (!currentUser) {
        return <Navigate to="/login" replace />;
    }
    const destination = getAuthDestination(currentUser);
    if (!currentUser.profile_completed && pathname !== destination) {
        return <Navigate to={destination} replace />;
    }
    return <Outlet/>;   
}

export default RequireAuth;
