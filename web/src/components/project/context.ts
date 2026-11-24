/**
 * 项目详情页上下文：详情页头部与各 Tab 面板共享的项目信息、我的项目角色。
 * 移交负责人后由设置面板就地更新 myRole，保证头部徽标同步。
 */

import type { InjectionKey, Ref } from 'vue'
import type { ProjectRole, ProjectView } from '@/types/team'

export interface ProjectContext {
  project: Ref<ProjectView | null>
  myRole: Ref<ProjectRole>
}

export const projectContextKey: InjectionKey<ProjectContext> = Symbol('project-context')
