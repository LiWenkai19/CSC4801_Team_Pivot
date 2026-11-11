import { requestWithToken } from './common_api'
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

/**
 * 删除职位：成功为 204 无响应体，由公共请求函数统一兼容；
 * 403（非本人职位）、404（不存在）、409（已有申请或面试时段）均以 ApiError 抛出，
 * 页面可按 status 区分处理。
 */
export function deleteJob(id: string): Promise<void> {
    return requestWithToken<void>(`employer/jobs/${encodeURIComponent(id)}`, 'DELETE')
}

export function listJobApplicants(id: string): Promise<ApplicantPublic[]> {
    return requestWithToken(`employer/jobs/${encodeURIComponent(id)}/applications`, 'GET')
}

export function changeApplicationStatus(id: string, data: ApplicationStatusUpdate): Promise<ApplicationStatusPublic> {
    return requestWithToken(`employer/applications/${encodeURIComponent(id)}/status`, 'PATCH', undefined, data)
}
