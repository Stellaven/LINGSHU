/**
 * 团队领域模型
 * TODO(backend): 以下字段为前端先行约定，后端就绪后以实际返回为准，联调时统一调整。
 */

/** 团队内身份 */
export type TeamRole = 'owner' | 'member'

/** 团队 */
export interface Team {
  id: string
  name: string
  description: string
  /** 创建时间（ISO 8601） */
  createdAt: string
}

/** 团队列表接口附带「我」在该团队中的身份 */
export type TeamWithRole = Team & { myRole: TeamRole }

/** 团队成员 */
export interface TeamMember {
  id: string
  teamId: string
  /** 登录账号 */
  account: string
  /** 我的团队内昵称 */
  nickname: string
  email: string
  role: TeamRole
  /** 加入时间（ISO 8601） */
  joinedAt: string
}

/** 成员分页查询结果 */
export interface MemberPage {
  items: TeamMember[]
  total: number
  page: number
  pageSize: number
}

/** 团队项目 */
export interface TeamProject {
  id: string
  teamId: string
  name: string
  description: string
  /** 负责人账号 */
  ownerAccount: string
  /** 成员数 */
  memberCount: number
  createdAt: string
  /** 自定义排序值（越小越靠前） */
  sortOrder: number
}

/** 项目视图：负责人昵称已在服务端按成员表解析 */
export interface ProjectView extends TeamProject {
  ownerName: string
}

/** 项目内身份 */
export type ProjectRole = 'owner' | 'member'

/** 项目成员 */
export interface ProjectMember {
  id: string
  projectId: string
  /** 登录账号 */
  account: string
  /** 我的项目内昵称 */
  nickname: string
  email: string
  role: ProjectRole
  /** 加入时间（ISO 8601） */
  joinedAt: string
}

/** 项目成员分页查询结果 */
export interface ProjectMemberPage {
  items: ProjectMember[]
  total: number
  page: number
  pageSize: number
}

/** 系统账号（添加团队成员时搜索选择用） */
export interface SystemAccount {
  id: string
  account: string
}
