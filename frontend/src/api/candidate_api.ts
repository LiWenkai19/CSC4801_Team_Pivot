import { requestWithToken } from './common_api'
import type { CandidateProfilePublic, CandidateProfileUpdate, RecommendedJob, CandidateApplication, InterviewSlot, BookingPublic } from '../types'

/** 候选人页面统一复用团队请求与认证，不维护第二套会话。 */
export function getMyProfile(): Promise<CandidateProfilePublic> {
    return requestWithToken('candidate/profile', 'GET')
}

export function updateMyProfile(data: CandidateProfileUpdate): Promise<CandidateProfilePublic> {
    return requestWithToken('candidate/profile', 'PATCH', undefined, data)
}

export function listJobs(): Promise<RecommendedJob[]> {
    return requestWithToken('candidate/jobs', 'GET')
}

export function getJob(id: string): Promise<RecommendedJob> {
    return requestWithToken(`candidate/jobs/${encodeURIComponent(id)}`, 'GET')
}

export function applyToJob(id: string): Promise<CandidateApplication> {
    return requestWithToken(`candidate/jobs/${encodeURIComponent(id)}/applications`, 'POST', undefined, {})
}

export function listApplications(): Promise<CandidateApplication[]> {
    return requestWithToken('candidate/applications', 'GET')
}

export function listAvailableSlots(id: string): Promise<InterviewSlot[]> {
    return requestWithToken(`candidate/applications/${encodeURIComponent(id)}/slots`, 'GET')
}

export function bookSlot(applicationId: string, slotId: string): Promise<BookingPublic> {
    return requestWithToken(`candidate/applications/${encodeURIComponent(applicationId)}/booking`, 'POST', undefined, { slot_id: slotId })
}
