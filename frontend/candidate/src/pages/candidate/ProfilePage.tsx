import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useRemote } from "../../hooks/useRemote";
import { candidateRequest } from "../../api/common_api";
import type {
  CandidateProfileCreate,
  CandidateProfilePublic,
} from "../../types";
import CandidateForm from "../users/CandidateForm";
import { ErrorMessage } from "../../components/candidate/ErrorMessage";
import { PlainText } from "../../components/PlainText";

/** 资料补填沿用队友的 /candidate/details；此页负责已有资料的查看与编辑。 */
export default function ProfilePage() {
  // 从会话取得当前用户；revision 改变会让 useRemote 重新读取资料。
  const { currentUser, refreshCurrentUser } = useAuth();
  const navigate = useNavigate();
  const [revision, refresh] = useState(0);
  const state = useRemote<CandidateProfilePublic>(
    `users/candidates/${currentUser!.id}/profile`,
    revision,
  );
  // 分别保存提交状态、错误提示和成功提示，供界面按当前状态显示。
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function save(profile: CandidateProfileCreate) {
    // PATCH 只修改当前账号的资料；服务端仍会独立校验身份和归属。
    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      await candidateRequest(
        `users/candidates/${currentUser!.id}/profile`,
        "PATCH",
        profile,
      );
      setMessage("资料已保存");
      // 数字递增触发重新加载，确保展示的简历与服务器保存结果一致。
      refresh((value) => value + 1);
    } catch (failure) {
      // 保存失败时留在页面并显示错误；finally 无论成功失败都解除提交状态。
      setError(
        failure instanceof Error ? failure.message : "保存失败，请重试。",
      );
    } finally {
      setSubmitting(false);
    }
  }

  // 加载中、加载失败、加载成功分别返回不同界面，避免读取尚不存在的数据。
  if (state.loading) return <p role="status">正在加载资料...</p>;
  if (!state.data)
    return (
      <section>
        <ErrorMessage error={state.error} />
        <button
          onClick={async () => {
            try {
              // 重新询问服务器是否已补全资料，再决定跳转补填页还是重试读取。
              const user = await refreshCurrentUser();
              if (!user.profile_completed)
                navigate("/candidate/details", { replace: true });
              else refresh((value) => value + 1);
            } catch (failure) {
              setError((failure as Error).message);
            }
          }}
        >
          重新检查资料状态
        </button>
        <ErrorMessage error={error} />
      </section>
    );
  // key 包含用户和版本：切换账号或重新读取时重新初始化表单输入。
  return (
    <main>
      <h2>我的资料</h2>
      <p>你和你已投递职位所属的雇主可以查看你的简历，只有你可以修改。推荐评分目前为占位，算法待开发。</p>
      <CandidateForm
        key={`${currentUser!.id}-${revision}`}
        initialProfile={state.data}
        submitLabel="保存资料"
        submitting={submitting}
        submitError={error}
        onSubmit={save}
      />
      <p role="status">{message}</p>
      <Link to="/candidate/jobs">查看职位推荐</Link>
      <h3>已保存的简历</h3>
      <PlainText>{state.data.resume_text || "暂未填写"}</PlainText>
    </main>
  );
}
