"""初始化基础数据（建表、预置演示账号、预置模型提供商目录）"""
import sys
from pathlib import Path

# 保证以 python scripts/init_data.py 运行时可导入项目包（app根目录入sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio  # noqa: E402

from sqlalchemy import select, text  # noqa: E402

from db.pg.pg_manager import Base, engine  # noqa: E402
from core.dependencies import get_db_session  # noqa: E402
from db.pg.orm_models import ModelProvider, User  # noqa: E402
from modules.auth import security  # noqa: E402
from modules.provider.constants import PROVIDER_CATALOG  # noqa: E402


async def init_tables():
    """按ORM模型建表（已存在则跳过）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def migrate_model_providers():
    """轻量迁移：为已存在的 model_providers 表补齐新增列（dev阶段create_all不会改表）"""
    stmts = [
        "ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS region TEXT NOT NULL DEFAULT 'global'",
        "ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS color TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS logo TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS default_base_url TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0",
    ]
    async with engine.begin() as conn:
        for stmt in stmts:
            await conn.execute(text(stmt))


async def migrate_project_knowledge_bases():
    """轻量迁移：为已存在的 project_knowledge_bases 表补齐新增列（dev阶段create_all不会改表）"""
    stmts = [
        "ALTER TABLE project_knowledge_bases ADD COLUMN IF NOT EXISTS embed_model TEXT NOT NULL DEFAULT 'bge-m3'",
        "ALTER TABLE project_knowledge_bases ADD COLUMN IF NOT EXISTS kag_project_id INTEGER",
        "ALTER TABLE file_parse_strategies ADD COLUMN IF NOT EXISTS graph_config JSONB",
    ]
    async with engine.begin() as conn:
        for stmt in stmts:
            await conn.execute(text(stmt))


async def migrate_model_instances():
    """轻量迁移：为已存在的 model_instances 表补齐项目关联与启用状态列"""
    stmts = [
        "ALTER TABLE model_instances ADD COLUMN IF NOT EXISTS project_id INTEGER",
        "ALTER TABLE model_instances ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT FALSE",
        "CREATE INDEX IF NOT EXISTS ix_model_instances_project_id ON model_instances (project_id)",
    ]
    async with engine.begin() as conn:
        for stmt in stmts:
            await conn.execute(text(stmt))


async def migrate_models():
    """轻量迁移：models 表的类型/上下文长度改为可空（未填写时留空，支持手动编辑）"""
    stmts = [
        "ALTER TABLE models ALTER COLUMN model_type DROP NOT NULL",
        "ALTER TABLE models ALTER COLUMN max_context_length DROP NOT NULL",
    ]
    async with engine.begin() as conn:
        for stmt in stmts:
            await conn.execute(text(stmt))


async def migrate_file_parse_strategies():
    """轻量迁移：file_parse_strategies 绑定知识库并补齐策略配置列（dev阶段create_all不会改表）"""
    stmts = [
        "ALTER TABLE file_parse_strategies ADD COLUMN IF NOT EXISTS kb_id INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE file_parse_strategies ADD COLUMN IF NOT EXISTS strategy_name TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE file_parse_strategies ADD COLUMN IF NOT EXISTS extractor TEXT NOT NULL DEFAULT 'auto'",
        "ALTER TABLE file_parse_strategies ADD COLUMN IF NOT EXISTS embed_model TEXT NOT NULL DEFAULT 'bge-m3'",
        "ALTER TABLE file_parse_strategies ADD COLUMN IF NOT EXISTS llm_model TEXT NOT NULL DEFAULT ''",
        # 编排序列（前置/后置提取与多级分块）；旧数据由 parser/chunker/extractor 派生
        "ALTER TABLE file_parse_strategies ADD COLUMN IF NOT EXISTS stages JSONB NOT NULL DEFAULT "
        "'{\"parser\": [], \"pre_extract\": [], \"split\": [], \"post_extract\": []}'::jsonb",
        # 历史列名 chunkers 对齐为 chunker（首次迁移时执行，已重命名则跳过）
        """DO $$
           BEGIN
               ALTER TABLE file_parse_strategies RENAME COLUMN chunkers TO chunker;
           EXCEPTION WHEN undefined_column THEN NULL;
           END $$""",
        "CREATE INDEX IF NOT EXISTS ix_file_parse_strategies_kb_id ON file_parse_strategies (kb_id)",
        # 策略名知识库内唯一（同名非约束索引会挡住ADD CONSTRAINT，先清掉改由约束承载）
        """DO $$
           BEGIN
               IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_kb_strategy_name') THEN
                   IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'uq_kb_strategy_name') THEN
                       DROP INDEX uq_kb_strategy_name;
                   END IF;
                   ALTER TABLE file_parse_strategies ADD CONSTRAINT uq_kb_strategy_name
                       UNIQUE (kb_id, strategy_name);
               END IF;
           END $$""",
    ]
    async with engine.begin() as conn:
        for stmt in stmts:
            await conn.execute(text(stmt))


async def seed_demo_user():
    """预置演示账号 demo/demo123，便于联调（生产环境禁止）"""
    async with get_db_session() as session:
        exists = (await session.execute(select(User).where(User.account == 'demo'))).scalar_one_or_none()
        if exists:
            print("演示账号已存在，跳过")
            return
        session.add(User(account='demo', password_hash=security.hash_password('demo123')))
        print("已创建演示账号: demo / demo123")


async def seed_model_providers():
    """预置模型提供商目录（按名称幂等：新增缺失项，已存在项补齐展示元数据）"""
    async with get_db_session() as session:
        existing = {
            provider.name: provider
            for provider in (await session.execute(select(ModelProvider))).scalars().all()
        }
        added = 0
        updated = 0
        for name, region, color, default_base_url, sort_order, logo in PROVIDER_CATALOG:
            provider = existing.get(name)
            if provider is None:
                session.add(ModelProvider(
                    name=name, region=region, color=color, logo=logo,
                    default_base_url=default_base_url, sort_order=sort_order,
                ))
                added += 1
                continue
            # 已存在：校正目录展示元数据（不触碰实例数据与提供商启用状态）
            fields = {
                'region': region,
                'color': color,
                'logo': logo,
                'default_base_url': default_base_url,
                'sort_order': sort_order,
            }
            changed = False
            for attr, value in fields.items():
                if getattr(provider, attr) != value:
                    setattr(provider, attr, value)
                    changed = True
            if changed:
                updated += 1
        print(f"模型提供商目录：新增 {added} 条，更新 {updated} 条，已存在 {len(existing)} 条")


async def main_async():
    await init_tables()
    await migrate_model_providers()
    await migrate_project_knowledge_bases()
    await migrate_model_instances()
    await migrate_models()
    await migrate_file_parse_strategies()
    await seed_demo_user()
    await seed_model_providers()
    await engine.dispose()


def main():
    asyncio.run(main_async())
    print("初始化完成")


if __name__ == "__main__":
    main()
