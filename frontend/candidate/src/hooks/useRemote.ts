import { useEffect, useState } from "react";
import { candidateRequest as request } from "../api/common_api";

export function useRemote<T>(path: string, revision = 0) {

  const [data, setData] = useState<T | null>(null);

  const [error, setError] = useState("");

  const [status, setStatus] = useState(0);

  const [loading, setLoading] = useState(true);

  useEffect(() => {

    let active = true;

    setLoading(true);

    setError("");

    setStatus(0);

    setData(null);

    request<T>(path)
      .then((value) => {

        if (active)

          setData(value);
      })
      .catch((e) => {

        if (active) {

          setError(e.message);

          setStatus(e.status ?? 0);
        }
      })
      .finally(() => {

        if (active)

          setLoading(false);
      });

    return () => {

      active = false;
    };
  }, [path, revision]);

  return { data, error, status, loading };
}
