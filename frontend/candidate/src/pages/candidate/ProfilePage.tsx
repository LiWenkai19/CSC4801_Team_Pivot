import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useRemote } from "../../hooks/useRemote";
import { candidateRequest } from "../../api/candidate_api";
import type {
  CandidateProfileCreate,
  CandidateProfilePublic,
} from "../../types";
import CandidateForm from "../users/CandidateForm";
import { ErrorMessage } from "../../components/candidate/ErrorMessage";
import { PlainText } from "../../components/PlainText";

/** 资料补填沿用队友的 /candidate/details；此页负责已有资料的查看与编辑。 */
export default function ProfilePage() {
  const { currentUser, refreshCurrentUser } = useAuth();
  const navigate = useNavigate();
  const [revision, refresh] = useState(0);
  const state = useRemote<CandidateProfilePublic>(
    `users/candidates/${currentUser!.id}/profile`,
    revision,
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function save(profile: CandidateProfileCreate) {
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
      refresh((value) => value + 1);
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "保存失败，请重试。",
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (state.loading) return <p role="status">正在加载资料...</p>;
  if (!state.data)
    return (
      <section>
        <ErrorMessage error={state.error} />
        <button
          onClick={async () => {
            try {
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
