import { useState } from "react";
import { Link } from "react-router-dom";
import type { Job } from "../../types";
import { useRemote } from "../../hooks/useRemote";
import { ErrorMessage } from "../../components/candidate/ErrorMessage";
import { ApplyButton } from "../../components/candidate/ApplyButton";
import { RecommendationScore } from "../../components/candidate/RecommendationScore";

function JobsPage() {

  const [revision, refresh] = useState(0);

  const state = useRemote<Job[]>("candidate/jobs", revision);

  return (
    <>
      <p className="eyebrow">EXPLORE OPPORTUNITIES</p>
      <h1>职位推荐</h1>
      <p>职位按匹配分数从高到低排列。评分算法待开发，目前统一为 0 分占位，不代表真实匹配程度；同分按职位名称排序。</p>
      {state.loading ? (
         <p>正在加载职位…</p>
      ) : state.error ? (
        <>
          <ErrorMessage
            error={
               state.error
            }
          />
          {state.status === 404 ? (
             <Link to="/candidate/profile">
              填写我的资料
            </Link>
          ) : (
             <button
              onClick={
                 () =>
                  refresh((n) => n + 1)
              }
            >
              重试
            </button>
          )}
        </>
      ) : (
        <>
          {!state.data?.length && (
             <p>暂时没有可申请的职位。</p>
          )}
          <div className="jobs">
            {state.data?.map((job) => (
               <article
                className="panel"
                key={
                   job.id
                }
              >
                <RecommendationScore score={job.score} />
                <h2>
                  <Link
                    to={
                       `/candidate/jobs/${job.id}`
                    }
                  >
                    {job.title}
                  </Link>
                </h2>
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
                <Link
                  to={
                     `/candidate/jobs/${job.id}`
                  }
                >
                  查看职位描述 →
                </Link>
                <ApplyButton
                  job={
                     job
                  }
                  onApplied={
                     () =>
                      refresh((n) => n + 1)
                  }
                />
              </article>
            ))}
          </div>
        </>
      )}
    </>
  );
}
export default JobsPage;
