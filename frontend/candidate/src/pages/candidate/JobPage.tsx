import { useState } from "react";
import { RecommendationScore } from "../../components/candidate/RecommendationScore";
import { Link, useParams } from "react-router-dom";
import type { Job } from "../../types";
import { useRemote } from "../../hooks/useRemote";
import { ErrorMessage } from "../../components/candidate/ErrorMessage";
import { ApplyButton } from "../../components/candidate/ApplyButton";
import { PlainText } from "../../components/PlainText";

function JobPage() {

  const { jobId } = useParams();

  const [revision, refresh] = useState(0);

  const state = useRemote<Job>(`candidate/jobs/${jobId}`, revision);

  if (state.loading)

    return  <p>正在加载职位…</p>;

  if (state.error || !state.data)

    return (
      <>
        <ErrorMessage
          error={
             state.error
          }
        />
        <Link to="/candidate/jobs">返回职位列表</Link>
      </>
    );

  const job = state.data;

  return (
    <>
      <Link to="/candidate/jobs">← 职位推荐</Link>
      <section className="panel">
        <RecommendationScore score={job.score} />
        <h1>
          {job.title}
        </h1>
        <p>
          {job.company_name}
        </p>
        <div className="skills">
          {job.required_skills.map((skill) => (
             <span
              key={
                 skill
              }
            >
              {skill}
            </span>
          ))}
        </div>
        <h2>职位描述</h2>
        <PlainText>
          {job.description}
        </PlainText>
        <ApplyButton
          job={
             job
          }
          onApplied={
             () =>
              refresh((n) => n + 1)
          }
        />
      </section>
    </>
  );
}
export default JobPage;
