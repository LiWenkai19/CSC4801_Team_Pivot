import { ErrorMessage } from "./ErrorMessage";

export const duplicateApplicationMessage = "你已申请该职位，请勿重复申请。";

export function ApplicationFeedback({ applied, error }: { applied: boolean; error: string }) {
  return applied ? (
    <p role="status">{duplicateApplicationMessage}</p>
  ) : (
    <ErrorMessage error={error} />
  );
}
