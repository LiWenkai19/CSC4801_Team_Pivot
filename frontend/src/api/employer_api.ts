import { requestWithToken } from './common_api'
import type {
    ApplicantPublic, ApplicationStatusPublic, ApplicationStatusUpdate,
    CompanyPublic, CompanyUpdate, InterviewSlot, JobCreate, JobPublic, JobUpdate, ManagedInterviewSlot,
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

/** 获取当前雇主尚未开始的时段及预约状态。 */
export function listMyInterviewSlots(): Promise<ManagedInterviewSlot[]> {
    return requestWithToken('employer/interview-slots', 'GET')
}

/** 提交带时区的开始时间，由后端计算结束时间。 */
export function createInterviewSlot(startsAt: string): Promise<InterviewSlot> {
    return requestWithToken('employer/interview-slots', 'POST', undefined, {
        starts_at: startsAt,
    })
}

/** 删除时段，公共请求层会处理 204 空响应。 */
export function deleteInterviewSlot(id: string): Promise<void> {
    return requestWithToken(`employer/interview-slots/${encodeURIComponent(id)}`, 'DELETE')
}
