import type {
    AuthResponse,
    CandidateProfileCreate,
    CandidateProfilePublic,
    EmployerProfileCreate,
    EmployerProfilePublic,
    Role,
    Token,
    UserPublic,
} from '../types'

const API_BASE_URL = 'http://127.0.0.1:8000/'

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

export async function request<T>(
    path: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    headers?: HeadersInit,
    body?: unknown,
): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers: {
            ...(body !== undefined
                ? { 'Content-Type': 'application/json' }
                : {}),
            ...headers,
        },
        body: body !== undefined
            ? JSON.stringify(body)
            : undefined,
    })

    await showError(response)

    return response.json() as Promise<T>
}

export async function requestWithToken<T>(
    path: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    headers?: HeadersInit,
    body?: unknown,
): Promise<T> {
    const token = localStorage.getItem('token')
    if (!token) {
        throw new Error('No token found')
    }
    const response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers: {
            // Authorization 必须无条件带上：GET/DELETE 没有 body，
            // 之前放在 body 判断里会导致这类请求缺少 token → 401
            'Authorization': `Bearer ${token}`,
            ...(body !== undefined
                ? { 'Content-Type': 'application/json' }
                : {}),
            ...headers,
        },
        body: body !== undefined
            ? JSON.stringify(body)
            : undefined,
    })

    await showError(response)

    return response.json() as Promise<T>
}

export async function fileRequest<T>(
    path: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    body: FormData,
    headers?: HeadersInit,
): Promise<T> {
    const token = localStorage.getItem('token')
    if (!token) {
        throw new Error('No token found')
    }
    const response = await fetch(`${API_BASE_URL}${path}`, {
        // 注意：不要手动设 Content-Type，浏览器会自动补上带 boundary 的
        // multipart/form-data，手写会导致后端解析不出文件
        method,
        headers: {
            'Authorization': `Bearer ${token}`,
            ...headers,
        },
        body
    })

    await showError(response)
    return response.json() as Promise<T>
}

/** JSON 登录，保存 Token，并返回后端提供的账户信息。 */
export async function login(
    email: string,
    password: string,
    remember_me = false,
): Promise<AuthResponse> {
    const response = await request<AuthResponse>('users/login', 'POST', {}, {
            "email": email,
            "password": password,
            "remember_me": remember_me
        }
    )
    localStorage.setItem('token', response.access_token)
    return response
}

export async function logout(): Promise<void> {
    localStorage.removeItem('token')
}

/** 读取账户公开信息；供认证上下文恢复登录状态。 */
export async function getUserPublic(): Promise<UserPublic> {
    return requestWithToken<UserPublic>('users/me', 'GET')
}

// 保留模板原来的名称，两个函数均对应 GET /users/me。
export async function getCurrentUser(): Promise<UserPublic> {
    return getUserPublic()
}

/** 注册时只提交账户信息；成功后保存 Token，供后续填写资料使用。 */
export async function createUser(
    email: string,
    password: string,
    role: Role,
): Promise<AuthResponse> {
    const response = await request<AuthResponse>('users/register', 'POST', {}, {
        "email": email,
        "password": password,
        "role": role
    })
    localStorage.setItem('token', response.access_token)
    return response
}

/** OAuth2 表单认证；与 Swagger 一致，username 字段实际传邮箱。 */
export async function loginForAccessToken(email: string, password: string): Promise<Token> {
    const body = new URLSearchParams({ username: email, password })
    const response = await fetch(`${API_BASE_URL}users/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
    })
    await showError(response)
    const token: Token = await response.json()
    localStorage.setItem('token', token.access_token)
    return token
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
