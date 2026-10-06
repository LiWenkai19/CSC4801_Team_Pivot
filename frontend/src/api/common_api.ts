import type { UserPublic, Token} from '../types'

const API_BASE_URL = 'http://127.0.0.1:8000/'

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

        throw new Error(message)
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

export async function login(email: string, password: string): Promise<Token> {
    const response = await request<Token>('users/login', 'POST', {}, {
            "email": email,
            "password": password,
            "remember_me": false
        }
    )
    localStorage.setItem('token', response.access_token)
    return response
}

export async function logout(): Promise<void> {
    localStorage.removeItem('token')
}

export async function getCurrentUser(): Promise<UserPublic> {
    const token = localStorage.getItem('token')
    if (!token) {
        throw new Error('No token found')
    }
    const response = await request<UserPublic>('users/me', 'GET', 
        { 'Authorization': `Bearer ${token}` }
    )
    return response
}

export async function createUser(email: string, password: string): Promise<void> {
    const response = await request<void>('users/register', 'POST', {}, {
        "email": email,
        "password": password
    })
    return response
}
