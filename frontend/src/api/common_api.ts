import type {
    AuthResponse,
    CandidateProfileCreate,
    CandidateProfilePublic,
    EmployerProfileCreate,
    EmployerProfilePublic,
    Role,
    UserPublic,
} from '../types'

// 同源路径：开发时由 Vite 代理把 /api 去掉前缀后转发到后端，浏览器不发生跨源请求。
const API_BASE_URL = '/api/'

// 会修改数据的方法，需要携带 CSRF 令牌。
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

/** 保留 HTTP 状态码，供页面区分资料重复创建等业务错误。 */
export class ApiError extends Error {
    readonly status: number

    /** 保存服务端消息和状态码，兼容现有 Error 错误处理。 */
    constructor(message: string, status: number) {
        super(message)
        this.name = 'ApiError'
        this.status = status
    }
}

/** 解析服务端错误消息，并保留状态码供页面决定恢复方式。 */
async function showError(response: Response){
    if (!response.ok) {
        const error = await response.json().catch(() => null)
        let message: string
        if (typeof error?.detail === 'string') {
            // 自定义业务错误：detail 是字符串
            message = error.detail
        } else if (Array.isArray(error?.detail)) {
            // FastAPI 422：detail 是校验错误数组，拼成可读文本
            message = error.detail
                .map((e: { loc: (string | number)[]; msg: string }) =>
                    `${e.loc.join('.')}: ${e.msg}`)
                .join('; ')
        } else {
            message = `Request failed with status ${response.status}`
        }

        throw new ApiError(message, response.status)
    }
}

/**
 * 读取后端下发的 CSRF 令牌（非 HttpOnly Cookie）。
 * 会话 Cookie 是 HttpOnly 的，JS 读不到——这正是它防 XSS 窃取的原因。
 */
function readCsrfToken(): string | undefined {
    const entry = document.cookie
        .split('; ')
        .find((item) => item.startsWith('csrf_token='))
    return entry ? decodeURIComponent(entry.slice('csrf_token='.length)) : undefined
}

/**
 * 统一发送请求。认证由浏览器自动携带的会话 Cookie 完成，前端不接触任何凭证；
 * 写请求自动附加 X-CSRF-Token 头。body 为 FormData 时按文件上传处理。
 */
async function send<T>(
    path: string,
    method: HttpMethod,
    headers?: HeadersInit,
    body?: unknown,
): Promise<T> {
    const isForm = body instanceof FormData
    const csrfToken = UNSAFE_METHODS.has(method) ? readCsrfToken() : undefined
    const response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        // 同源请求默认就会带 Cookie，这里写明是为了表达意图。
        credentials: 'same-origin',
        headers: {
            // FormData 不能手动设 Content-Type，浏览器会自动补上带 boundary 的 multipart/form-data
            ...(body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : {}),
            ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
            ...headers,
        },
        body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    })

    await showError(response)

    // 204 No Content（如删除职位、登出）没有响应体。
    if (response.status === 204) {
        return undefined as T
    }
    return response.json() as Promise<T>
}

/** 无需登录的请求（登录、注册）；会话 Cookie 仍由浏览器自动管理。 */
export async function request<T>(
    path: string,
    method: HttpMethod,
    headers?: HeadersInit,
    body?: unknown,
): Promise<T> {
    return send<T>(path, method, headers, body)
}

/**
 * 需要登录的请求。保留原名和参数顺序，业务 API 无需改动；
 * 认证已改为 HttpOnly 会话 Cookie，未登录时由后端返回 401。
 */
export async function requestWithToken<T>(
    path: string,
    method: HttpMethod,
    headers?: HeadersInit,
    body?: unknown,
): Promise<T> {
    return send<T>(path, method, headers, body)
}

/** 文件上传；Content-Type 由浏览器根据 FormData 自动设置。 */
export async function fileRequest<T>(
    path: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    body: FormData,
    headers?: HeadersInit,
): Promise<T> {
    return send<T>(path, method, headers, body)
}

/** JSON 登录；会话由后端通过 Set-Cookie 建立，响应体只含账户信息。 */
export async function login(
    email: string,
    password: string,
    remember_me = false,
): Promise<AuthResponse> {
    return request<AuthResponse>('users/login', 'POST', {}, {
        "email": email,
        "password": password,
        "remember_me": remember_me
    })
}

/** 通知后端删除会话并清除 Cookie；只删前端状态无法让会话失效。 */
export async function logout(): Promise<void> {
    await request<void>('users/logout', 'POST')
}

/** 读取账户公开信息；这是前端判断"是否已登录"的唯一依据。 */
export async function getUserPublic(): Promise<UserPublic> {
    return requestWithToken<UserPublic>('users/me', 'GET')
}

// 保留模板原来的名称，两个函数均对应 GET /users/me。
export async function getCurrentUser(): Promise<UserPublic> {
    return getUserPublic()
}

/** 注册时只提交账户信息；后端注册成功即建立会话，供后续填写资料使用。 */
export async function createUser(
    email: string,
    password: string,
    role: Role,
): Promise<AuthResponse> {
    return request<AuthResponse>('users/register', 'POST', {}, {
        "email": email,
        "password": password,
        "role": role
    })
}

/** 首次保存当前候选人的资料；简历、技能可以省略。 */
export async function createCandidateProfile(
    profile: CandidateProfileCreate,
): Promise<CandidateProfilePublic> {
    return requestWithToken<CandidateProfilePublic>(
        'users/candidate/profile', 'POST', {}, profile,
    )
}

/** 首次保存当前雇主的公司资料；公司描述可以省略。 */
export async function createEmployerProfile(
    profile: EmployerProfileCreate,
): Promise<EmployerProfilePublic> {
    return requestWithToken<EmployerProfilePublic>(
        'users/employer/profile', 'POST', {}, profile,
    )
}
