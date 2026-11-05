import { ApiError, requestWithToken } from './common_api'
import type {
    ApplicantPublic, ApplicationStatusPublic, ApplicationStatusUpdate,
    CompanyPublic, CompanyUpdate, JobCreate, JobPublic, JobUpdate,
} from '../types'

/** 雇主操作复用统一鉴权与错误解析，页面不直接发请求。 */
export function getMyCompany(): Promise<CompanyPublic> {
    return requestWithToken('employer/company', 'GET')
}

export function updateMyCompany(data: CompanyUpdate): Promise<CompanyPublic> {
    return requestWithToken('employer/company', 'PATCH', undefined, data)
}

export function createJob(data: JobCreate): Promise<JobPublic> {
    return requestWithToken('employer/jobs', 'POST', undefined, data)
}

export function listMyJobs(): Promise<JobPublic[]> {
    return requestWithToken('employer/jobs', 'GET')
}

export function getMyJob(id: string): Promise<JobPublic> {
    return requestWithToken(`employer/jobs/${encodeURIComponent(id)}`, 'GET')
}

export function updateJob(id: string, data: JobUpdate): Promise<JobPublic> {
    return requestWithToken(`employer/jobs/${encodeURIComponent(id)}`, 'PATCH', undefined, data)
}

/** DELETE 成功没有 JSON 响应体，在本模块兼容 204。 */
export async function deleteJob(id: string): Promise<void> {
    const token = localStorage.getItem('token')
    if (!token) throw new ApiError('No token found', 401)
    const response = await fetch(`http://127.0.0.1:8000/employer/jobs/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) {
        const error = await response.json().catch(() => null)
        let message = `Request failed with status ${response.status}`
        if (typeof error?.detail === 'string') message = error.detail
        else if (Array.isArray(error?.detail)) {
            message = error.detail.map((entry: { loc: (string | number)[]; msg: string }) => `${entry.loc.join('.')}: ${entry.msg}`).join('; ')
        }
        throw new ApiError(message, response.status)
    }
}

export function listJobApplicants(id: string): Promise<ApplicantPublic[]> {
    return requestWithToken(`employer/jobs/${encodeURIComponent(id)}/applications`, 'GET')
}

export function changeApplicationStatus(id: string, data: ApplicationStatusUpdate): Promise<ApplicationStatusPublic> {
    return requestWithToken(`employer/applications/${encodeURIComponent(id)}/status`, 'PATCH', undefined, data)
}
