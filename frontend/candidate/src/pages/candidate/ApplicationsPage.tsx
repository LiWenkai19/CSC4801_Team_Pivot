import { useState } from "react";
import { Link } from "react-router-dom";
import type { Application, Slot } from "../../types";
import { useRemote } from "../../hooks/useRemote";
import { ErrorMessage } from "../../components/candidate/ErrorMessage";
import { ApiError } from "../../api/common_api";
import { candidateRequest as request } from "../../api/common_api";

const statusLabels = {

  Pending: "待处理",

  Interviewing: "面试中",

  Rejected: "已拒绝",

  Accepted: "已录用",
};

const slotTime = (value: string) =>
  new Intl.DateTimeFormat("zh-CN", {

    timeZone: "Asia/Shanghai",

    dateStyle: "medium",

    timeStyle: "short",
  }).format(new Date(value));

function BookingPanel({
  application,
  onBooked,
}: {

  application: Application;

  onBooked: () => void;
}) {

  const [revision, refresh] = useState(0);

  const state = useRemote<Slot[]>(
    `candidate/applications/${application.id}/slots`,
    revision,
  );

  const [busy, setBusy] = useState(false);

  const [error, setError] = useState("");

  return (
     <section>
      <h3>选择面试时段</h3>
      <p>以下时间均为 Asia/Shanghai（UTC+8）。</p>
      {state.loading ? (
         <p>正在加载时段…</p>
      ) : state.error ? (
        <>
          <ErrorMessage
            error={
               state.error
            }
          />
          <button
            onClick={
               () =>
                refresh((n) => n + 1)
            }
          >
            刷新时段
          </button>
        </>
      ) : (
        <>
          {!state.data?.length && (
             <p>暂无可用时段。</p>
          )}
          {state.data?.map((slot) => (
             <div
              className="slot"
              key={
                 slot.id
              }
            >
              <span>
                {slotTime(slot.starts_at)}
                {" — "}
                {slotTime(slot.ends_at)}
              </span>
              <button
                disabled={
                   busy
                }
                onClick={
                   async () => {

                    setBusy(true);

                    setError("");

                    try {

                      await request(
                        `candidate/applications/${application.id}/booking`,
                        "POST",
                        {

                          slot_id: slot.id,
                        },
                      );

                      onBooked();
                    } catch (e) {


                      setError((e as Error).message);

                      if (e instanceof ApiError && e.status === 409)

                        refresh((n) => n + 1);
                    } finally {

                      setBusy(false);
                    }
                  }
                }
              >
                预约
              </button>
            </div>
          ))}
        </>
      )}
      <ErrorMessage
        error={
           error
        }
      />
    </section>
  );
}

function ApplicationsPage() {

  const [revision, refresh] = useState(0);

  const state = useRemote<Application[]>("candidate/applications", revision);

  const [selected, setSelected] = useState<string | null>(null);

  return (
    <>
      <p className="eyebrow">YOUR PROGRESS</p>
      <h1>我的申请</h1>
      {state.loading ? (
         <p>正在加载申请…</p>
      ) : state.error ? (
        <>
          <ErrorMessage
            error={
               state.error
            }
          />
          <button
            onClick={
               () =>
                refresh((n) => n + 1)
            }
          >
            重试
          </button>
        </>
      ) : (
        <>
          {!state.data?.length && (
             <p>
              尚未申请职位。
              <Link to="/candidate/jobs">浏览职位</Link>
            </p>
          )}
          {state.data?.map((application) => (
             <article
              className="panel"
              key={
                 application.id
              }
            >
              <span className="badge">
                {statusLabels[application.status]}
              </span>
              <h2>
                {application.title}
              </h2>
              <p>
                {application.company_name}
              </p>
              {application.booking ? (
                 <p role="status">
                  已预约：
                  {slotTime(application.booking.starts_at)} —
                  {/**/}{" "}
                  {slotTime(application.booking.ends_at)}
                  （Asia/Shanghai，UTC+8）
                </p>
              ) : (
                application.status === "Interviewing" && (
                  <>
                    <button
                      onClick={
                         () =>
                          setSelected(
                            selected === application.id ? null : application.id,
                          )
                      }
                    >
                      选择面试时段
                    </button>
                    {selected === application.id && (
                       <BookingPanel
                        application={
                           application
                        }
                        onBooked={
                           () => {

                            setSelected(null);

                            refresh((n) => n + 1);
                          }
                        }
                      />
                    )}
                  </>
                )
              )}
            </article>
          ))}
        </>
      )}
    </>
  );
}
export default ApplicationsPage;
