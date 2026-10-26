import { requestWithToken } from "./common_api";

/** 保留队友的请求参数顺序；候选人页面只需提供路径、方法和 JSON 数据。 */
export function candidateRequest<T>(
  path: string,
  method: "GET" | "POST" | "PATCH" = "GET",
  body?: unknown,
): Promise<T> {
  return requestWithToken<T>(path, method, {}, body);
}
