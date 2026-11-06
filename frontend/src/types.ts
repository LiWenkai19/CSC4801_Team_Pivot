/** 与后端 Role 枚举的 JSON 值保持一致。 */
export type Role = 'candidate' | 'employer'

/** 注册仅提交账户凭据和角色，资料在注册后单独填写。 */
export interface UserCreate {
  email: string
  /** 非空密码；具体约束由服务端校验。 */
  password: string
  role: Role
}

/** 登录已有账户；省略 remember_me 时，服务端默认为 false。 */
export interface UserLogin {
  email: string
  /** 非空密码；具体约束由服务端校验。 */
  password: string
  remember_me?: boolean
}

/** 账户响应；UUID 和邮箱在 JSON 中均为字符串。 */
export interface UserPublic {
  id: string
  email: string
  role: Role
  profile_completed: boolean
}

/** 认证成功后签发的访问令牌。 */
export interface Token {
  access_token: string
  token_type: 'bearer'
}

/** 认证响应包含访问令牌和账户信息。 */
export interface AuthResponse extends Token {
  user: UserPublic
}

/** 首次填写候选人资料；省略简历和技能时，服务端使用空字符串和空列表。 */
export interface CandidateProfileCreate {
  /** 服务端去除首尾空白后，名称必须非空。 */
  display_name: string
  resume_text?: string
  skills?: string[]
}

/** 首次填写雇主资料；省略公司描述时，服务端使用空字符串。 */
export interface EmployerProfileCreate {
  /** 服务端去除首尾空白后，名称必须非空。 */
  company_name: string
  company_description?: string
}

/** 候选人本人资料响应，包含后端规范化后的技能。 */
export interface CandidateProfilePublic {
  user_id: string
  display_name: string
  resume_text: string
  skills: string[]
}

/** 雇主公司资料响应。 */
export interface EmployerProfilePublic {
  user_id: string
  company_name: string
  company_description: string
}

/** 雇主公司接口与资料表使用相同字段。 */
export interface CompanyPublic extends EmployerProfilePublic {}

/** 省略字段表示不修改；不发送 null。 */
export interface CompanyUpdate {
  company_name?: string
  company_description?: string
}

export interface JobCreate {
  title: string
  description: string
  required_skills?: string[]
}

/** 技能传入时整体替换，空数组表示清空。 */
export interface JobUpdate {
  title?: string
  description?: string
  required_skills?: string[]
}

export interface JobPublic {
  id: string
  company_name: string
  employer_id: string
  title: string
  description: string
  required_skills: string[]
  created_at: string
  updated_at: string
}

export type ApplicationStatus = 'Pending' | 'Interviewing' | 'Rejected' | 'Accepted'

export interface BookingPublic {
  booking_id: string
  slot_id: string
  starts_at: string
  ends_at: string
}

/** 不包含候选人私有简历等信息；分数及顺序由服务端决定。 */
export interface ApplicantPublic {
  application_id: string
  candidate_id: string
  display_name: string
  skills: string[]
  match_score: number
  status: ApplicationStatus
  booking: BookingPublic | null
}

export interface ApplicationStatusUpdate {
  status: ApplicationStatus
}

export interface ApplicationStatusPublic {
  application_id: string
  job_id: string
  candidate_id: string
  status: ApplicationStatus
  updated_at: string
}

/** 省略字段保留原值；空字符串或空数组清空，不接受 null。 */
export interface CandidateProfileUpdate {
  display_name?: string
  resume_text?: string
  skills?: string[]
}

export interface RecommendedJob extends JobPublic {
  match_score: number
  applied: boolean
}

export interface CandidateApplication {
  application_id: string
  job_id: string
  job_title: string
  company_name: string
  status: ApplicationStatus
  created_at: string
  booking: BookingPublic | null
}

export interface InterviewSlot {
  id: string
  starts_at: string
  ends_at: string
}
