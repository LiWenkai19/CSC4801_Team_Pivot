import CandidateDetailsPage from './pages/users/CandidateDetailsPage';
import EmployerDetailsPage from './pages/users/EmployerDetailsPage';
import LoginPage from './pages/users/LoginPage';
import { Route, Routes, Navigate } from 'react-router-dom';
import NavPage from './pages/NavPage';  // Import the NavPage component here
import RegisterPage from './pages/users/RegisterPage';  // Import the RegisterPage component here
import RequireAuth from './components/RequireAuth';  // Import the RequiredAuth component here


/** 注册页面入口，两种角色的资料页沿用现有登录守卫。 */
function App() {
    return(
        <Routes>
            <Route path="/" element={<Navigate to="/login" replace />} />
            <Route path="/login" element={<LoginPage/>}></Route>
            <Route path="/register" element={<RegisterPage/>}></Route>

            <Route element={<RequireAuth />}>
                <Route path='/candidate/details' element={<CandidateDetailsPage />}></Route>
                <Route path='/employer/details' element={<EmployerDetailsPage />}></Route>
                <Route path='/navpage' element={<NavPage />}></Route>
            </Route>
       </Routes>
    )
}

export default App;
