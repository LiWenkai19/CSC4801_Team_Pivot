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
