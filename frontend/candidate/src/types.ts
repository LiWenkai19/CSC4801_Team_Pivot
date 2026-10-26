/** 原有账户与资料契约从团队类型模块复用，只在本文件增加候选人业务类型。 */
export type {
  Role, UserCreate, UserLogin, UserPublic, Token, AuthResponse,
  CandidateProfileCreate, CandidateProfilePublic,
  EmployerProfileCreate, EmployerProfilePublic,
} from '../../src/types'

/** 候选人职位列表/详情的统一响应；分数由后端共享匹配函数计算。 */
export interface Job {
  id: string; employer_id: string; title: string; description: string
  company_name: string; required_skills: string[]; score: number; applied: boolean
  score_kind: 'placeholder'
}
/** API 时间包含明确时区，页面统一显示 Asia/Shanghai。 */
export interface Slot { id: string; starts_at: string; ends_at: string }
export interface Booking extends Slot { slot_id: string }
export type ApplicationStatus = 'Pending' | 'Interviewing' | 'Rejected' | 'Accepted'
export interface Application {
  id: string; job_id: string; title: string; company_name: string
  status: ApplicationStatus; booking: Booking | null
}
