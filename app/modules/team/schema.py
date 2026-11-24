"""团队域入参模型（出参按前端契约返回camelCase，见 api/team_api.py 各接口返回）"""

from typing import Optional

from pydantic import BaseModel, Field


class CreateTeamRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64, description='团队名称')
    description: str = Field(default='', max_length=512, description='团队描述')


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64, description='项目名称')
    description: str = Field(default='', max_length=512, description='项目描述')
    owner_account: Optional[str] = Field(default=None, max_length=64, description='项目负责人账号，缺省为当前用户')


class CreateProjectKnowledgeBaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64, description='知识库名称')
    description: str = Field(default='', max_length=512, description='知识库描述')
    embed_model: str = Field(default='bge-m3', min_length=1, max_length=128, description='向量模型')


class AddMemberRequest(BaseModel):
    account: str = Field(min_length=1, max_length=64, description='系统账号')
