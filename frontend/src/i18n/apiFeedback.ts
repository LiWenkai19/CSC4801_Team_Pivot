import { ApiError } from '../api/common_api'
import type { MessageKey } from './zh-CN'

const knownDetails = new Map<string, MessageKey>([
    ['Invalid credentials', 'auth.invalidCredentials'],
    ['User already exists', 'auth.accountExists'],
    ['Company not found', 'api.companyMissing'],
    ['Company required', 'api.companyRequired'],
    ['Candidate profile not found', 'api.profileMissing'],
    ['Employer profile not found', 'api.companyMissing'],
    ['Job not found', 'api.jobMissing'],
    ['Application not found', 'api.applicationMissing'],
    ['Slot not found', 'api.slotMissing'],
    ['Slot already booked', 'booking.conflict'],
    ['Application already booked', 'api.applicationBooked'],
    ['Application must be Interviewing', 'api.interviewingRequired'],
    ['Slot is in the past', 'api.slotPast'],
    ['Slot must last 30 minutes', 'api.slotLength'],
    ['Slot must start in the future', 'slots.future'],
    ['Slot end time is out of range', 'api.slotOutOfRange'],
    ['Slot overlaps an existing slot', 'slots.overlap'],
])

/** 在界面选择错误文案，保留原请求封装与页面已有的业务分支。 */
export function apiFeedback(reason: unknown, fallback: MessageKey): MessageKey {
    if (reason instanceof TypeError) return 'api.network'
    if (!(reason instanceof ApiError)) return fallback

    const known = knownDetails.get(reason.message)
    if (known) return known
    switch (reason.status) {
        case 401: return 'api.session'
        case 403: return 'api.forbidden'
        case 422: return 'api.invalidInput'
        default: return fallback
    }
}
