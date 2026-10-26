import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

/** 外层 RequireAuth 负责登录与补填；这里阻止雇主进入候选人业务界面。 */
export default function RequireCandidate() {
  const { currentUser, logout } = useAuth();
  if (currentUser?.role !== "candidate")
    return (
      <main>
        <h2>禁止访问</h2>
        <p role="alert">此工作区仅供候选人使用。</p>
        <Link to="/navpage">返回主页</Link>
      </main>
    );
  return (
    <>
      <nav aria-label="候选人导航">
        <Link to="/navpage">主页</Link>
        {" | "}
        <Link to="/candidate/profile">我的资料</Link>
        {" | "}
        <Link to="/candidate/jobs">职位推荐</Link>
        {" | "}
        <Link to="/candidate/applications">我的申请</Link>
        {" | "}
        <button onClick={logout}>注销</button>
      </nav>
      <Outlet key={currentUser.id} />
    </>
  );
}
