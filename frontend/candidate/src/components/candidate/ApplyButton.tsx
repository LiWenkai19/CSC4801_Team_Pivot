import { useState } from "react";
import type { Job } from "../../types";
import { ApiError } from "../../api/common_api";
import { candidateRequest as request } from "../../api/common_api";
import { ApplicationFeedback, duplicateApplicationMessage } from "./ApplicationFeedback";

export function ApplyButton({
  job,
  onApplied,
}: {

  job: Job;
  onApplied: () => void;
}) {

  const [busy, setBusy] = useState(false);

  const [error, setError] = useState("");

  return (
     <div>
      <button
        disabled={
           busy ||
          job.applied
        }
        onClick={
           async () => {

            setBusy(true);

            setError("");

            try {

              await request(
                `candidate/jobs/${job.id}/applications`,
                "POST",
                {},
              );

              onApplied();
            } catch (e) {


              setError(e instanceof ApiError && e.status === 409
                ? duplicateApplicationMessage
                : (e as Error).message);

              if (e instanceof ApiError && e.status === 409)

                onApplied();
            } finally {

              setBusy(false);
            }
          }
        }
      >
        {job.applied ? "已申请" : busy ? "提交中…" : "申请职位"}
      </button>
      <ApplicationFeedback
        applied={job.applied}
        error={
           error
        }
      />
    </div>
  );
}
