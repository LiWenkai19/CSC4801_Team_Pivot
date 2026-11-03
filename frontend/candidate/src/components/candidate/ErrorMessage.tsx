
export function ErrorMessage({
  error,
}: {

  error: string;
}) {

  return error ? (
     <p
      role="alert"
      className="error"
    >
      {error}
    </p>
  ) : null;
}
