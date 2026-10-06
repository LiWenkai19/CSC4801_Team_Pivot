import React from "react";
import { Navigate , Outlet } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

function RequireAuth() {
    const auth = useAuth();
    const { currentUser, loading } = auth;

    if (loading) {
        return <div>Loading...</div>;
    };

    if (!currentUser) {
        return <Navigate to="/login" replace />;
    }
    return <Outlet/>;   
}

export default RequireAuth;
