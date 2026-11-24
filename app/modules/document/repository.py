"""
PostgreSQL DocumentStore，适配 llama-index-core 0.14.x 的 BaseDocumentStore 接口。

设计说明：
- 复用 db/pg/pg_manager.LlamaDocstoreNode 单表：node本体（JSONB）、doc_hash、ref_doc_id；
  派生数据（ref_doc_info / document_hashes）全部由SQL直接查询，无需额外表。
- 异步方法为原生实现（AsyncSession），同步方法通过 asyncio_run 桥接：
  llama_index 同步入口（如 VectorStoreIndex.from_documents、IngestionPipeline.run）
  内部会调用同步 add_documents，此时若已处于运行中的事件循环，asyncio_run
  会自动切到独立线程执行。
- 使用独立引擎 + NullPool：asyncpg连接与事件循环绑定，NullPool保证连接
  不会被跨事件循环（主循环 / asyncio_run线程循环）复用，避免
  "attached to a different loop" 错误。
- node_json 直接存 doc_to_json() 的dict（含 __type__ 判别字段），
  读取时用 json_to_doc 还原为正确的Node子类（TextNode/Document/IndexNode...）。
"""

from typing import Any, Coroutine, Dict, List, Optional, Sequence

from llama_index.core.async_utils import asyncio_run
from llama_index.core.schema import BaseNode
from llama_index.core.storage.docstore.types import (
    DEFAULT_BATCH_SIZE,
    BaseDocumentStore,
    RefDocInfo,
)
from llama_index.core.storage.docstore.utils import doc_to_json, json_to_doc
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config.settings import settings
from db.pg.orm_models import LlamaDocstoreNode
from db.pg.pg_manager import to_async_url

# DB语句分块上限（batch_size参数缺省时使用），避免单条SQL绑定参数过多
_DEFAULT_DB_CHUNK = 512

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker] = None


def _get_session_factory() -> async_sessionmaker:
    """惰性创建docstore专用session工厂（独立引擎 + NullPool，理由见模块docstring）"""
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_async_engine(to_async_url(settings.POSTGRESQL), poolclass=NullPool)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


class PostgresDocumentStore(BaseDocumentStore):
    """
    SQLAlchemy版Postgres Docstore，用于HierarchicalNodeParser父子检索，存储全部层级Node。

    用法：PostgresDocumentStore() —— 无需参数，通过全局配置 settings.POSTGRESQL 连接。
    """

    def __init__(self, batch_size: int = _DEFAULT_DB_CHUNK) -> None:
        self._session_factory = _get_session_factory()
        self._batch_size = batch_size

    # ========== 内部工具 ==========
    @staticmethod
    def _run(coro: Coroutine) -> Any:
        """同步方法桥接：无事件循环时直接运行，已有运行中循环时切线程执行"""
        return asyncio_run(coro)

    def _chunk(self, batch_size: Optional[int]) -> int:
        if batch_size and batch_size > 1:
            return batch_size
        return self._batch_size

    @staticmethod
    def _node_to_row(node: BaseNode, store_text: bool) -> dict:
        return {
            "node_id": node.node_id,
            "ref_doc_id": node.ref_doc_id,
            "doc_hash": node.hash,
            "node_json": doc_to_json(node) if store_text else None,
        }

    async def _bulk_upsert(self, rows: Sequence[dict], chunk_size: int) -> None:
        """批量upsert（存在则更新，不存在插入），按chunk分块执行"""
        async with self._session_factory() as session:
            for i in range(0, len(rows), chunk_size):
                stmt = pg_insert(LlamaDocstoreNode).values(list(rows[i : i + chunk_size]))
                stmt = stmt.on_conflict_do_update(
                    index_elements=[LlamaDocstoreNode.node_id],
                    set_={
                        "ref_doc_id": stmt.excluded.ref_doc_id,
                        "doc_hash": stmt.excluded.doc_hash,
                        "node_json": stmt.excluded.node_json,
                    },
                )
                await session.execute(stmt)
            await session.commit()

    # ===== Save/load =====
    def persist(self, persist_path: str = "", fs: Optional[Any] = None) -> None:
        """Postgres实时落库，无需本地持久化"""

    # ===== Main interface =====
    @property
    def docs(self) -> Dict[str, BaseNode]:
        return self._run(self.aget_all_documents())

    async def aget_all_documents(self) -> Dict[str, BaseNode]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(LlamaDocstoreNode.node_json).where(
                    LlamaDocstoreNode.node_json.isnot(None)
                )
            )
            docs: Dict[str, BaseNode] = {}
            for (node_json,) in result:
                node = json_to_doc(node_json)
                docs[node.node_id] = node
            return docs

    def add_documents(
        self,
        docs: Sequence[BaseNode],
        allow_update: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
        store_text: bool = True,
    ) -> None:
        self._run(self.async_add_documents(docs, allow_update, batch_size, store_text))

    async def async_add_documents(
        self,
        docs: Sequence[BaseNode],
        allow_update: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
        store_text: bool = True,
    ) -> None:
        if not docs:
            return
        # dict按node_id去重（同id保留最后一个），也避免ON CONFLICT同批重复主键报错
        rows = {node.node_id: self._node_to_row(node, store_text) for node in docs}
        if not allow_update:
            async with self._session_factory() as session:
                existing = (
                    (
                        await session.execute(
                            select(LlamaDocstoreNode.node_id).where(
                                LlamaDocstoreNode.node_id.in_(rows.keys())
                            )
                        )
                    )
                    .scalars()
                    .first()
                )
            if existing:
                raise ValueError(
                    f"node_id {existing} already exists. "
                    "Set allow_update to True to overwrite."
                )
        await self._bulk_upsert(list(rows.values()), self._chunk(batch_size))

    def get_document(self, doc_id: str, raise_error: bool = True) -> Optional[BaseNode]:
        return self._run(self.aget_document(doc_id, raise_error))

    async def aget_document(
        self, doc_id: str, raise_error: bool = True
    ) -> Optional[BaseNode]:
        async with self._session_factory() as session:
            node_json = (
                await session.execute(
                    select(LlamaDocstoreNode.node_json).where(
                        LlamaDocstoreNode.node_id == doc_id
                    )
                )
            ).scalar()
        if node_json is None:
            if raise_error:
                raise ValueError(f"doc_id {doc_id} not found.")
            return None
        return json_to_doc(node_json)

    def get_documents(
        self, node_ids: Sequence[str], raise_error: bool = True
    ) -> Dict[str, BaseNode]:
        return self._run(self.aget_documents(list(node_ids), raise_error))

    async def aget_documents(
        self, doc_ids: List[str], raise_error: bool = True
    ) -> Dict[str, BaseNode]:
        """单条SQL批量取节点（HierarchicalNodeParser父子批量检索用）"""
        if not doc_ids:
            return {}
        async with self._session_factory() as session:
            result = await session.execute(
                select(LlamaDocstoreNode.node_json).where(
                    LlamaDocstoreNode.node_id.in_(doc_ids),
                    LlamaDocstoreNode.node_json.isnot(None),
                )
            )
            nodes = [json_to_doc(row[0]) for row in result]
        found = {node.node_id: node for node in nodes}
        if raise_error:
            missing = set(doc_ids) - found.keys()
            if missing:
                raise ValueError(f"doc_ids {sorted(missing)} not found.")
        return found

    def delete_document(self, doc_id: str, raise_error: bool = True) -> None:
        self._run(self.adelete_document(doc_id, raise_error))

    async def adelete_document(self, doc_id: str, raise_error: bool = True) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                delete(LlamaDocstoreNode).where(LlamaDocstoreNode.node_id == doc_id)
            )
            await session.commit()
        if result.rowcount == 0 and raise_error:
            raise ValueError(f"doc_id {doc_id} not found.")

    def delete_documents(
        self, node_ids: Sequence[str], raise_error: bool = True
    ) -> None:
        self._run(self.adelete_documents(list(node_ids), raise_error))

    async def adelete_documents(
        self, doc_ids: List[str], raise_error: bool = True
    ) -> None:
        if not doc_ids:
            return
        async with self._session_factory() as session:
            result = await session.execute(
                delete(LlamaDocstoreNode).where(LlamaDocstoreNode.node_id.in_(doc_ids))
            )
            await session.commit()
        if result.rowcount < len(set(doc_ids)) and raise_error:
            raise ValueError(f"some of doc_ids {doc_ids} not found.")

    def document_exists(self, doc_id: str) -> bool:
        return self._run(self.adocument_exists(doc_id))

    async def adocument_exists(self, doc_id: str) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                select(LlamaDocstoreNode.node_id).where(
                    LlamaDocstoreNode.node_id == doc_id
                )
            )
            return result.scalar() is not None

    # ===== Hash =====
    def set_document_hash(self, doc_id: str, doc_hash: str) -> None:
        self._run(self.aset_document_hash(doc_id, doc_hash))

    async def aset_document_hash(self, doc_id: str, doc_hash: str) -> None:
        stmt = pg_insert(LlamaDocstoreNode).values(
            node_id=doc_id, doc_hash=doc_hash, ref_doc_id=None, node_json=None
        )
        # 只更新doc_hash，避免覆盖已存在节点的内容
        stmt = stmt.on_conflict_do_update(
            index_elements=[LlamaDocstoreNode.node_id],
            set_={"doc_hash": stmt.excluded.doc_hash},
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    def set_document_hashes(self, doc_hashes: Dict[str, str]) -> None:
        self._run(self.aset_document_hashes(doc_hashes))

    async def aset_document_hashes(self, doc_hashes: Dict[str, str]) -> None:
        """批量upsert hash（IngestionPipeline批量去重用）"""
        if not doc_hashes:
            return
        rows = [
            {
                "node_id": doc_id,
                "doc_hash": doc_hash,
                "ref_doc_id": None,
                "node_json": None,
            }
            for doc_id, doc_hash in doc_hashes.items()
        ]
        async with self._session_factory() as session:
            chunk = self._chunk(None)
            for i in range(0, len(rows), chunk):
                stmt = pg_insert(LlamaDocstoreNode).values(rows[i : i + chunk])
                stmt = stmt.on_conflict_do_update(
                    index_elements=[LlamaDocstoreNode.node_id],
                    set_={"doc_hash": stmt.excluded.doc_hash},
                )
                await session.execute(stmt)
            await session.commit()

    def get_document_hash(self, doc_id: str) -> Optional[str]:
        return self._run(self.aget_document_hash(doc_id))

    async def aget_document_hash(self, doc_id: str) -> Optional[str]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(LlamaDocstoreNode.doc_hash).where(
                    LlamaDocstoreNode.node_id == doc_id
                )
            )
            return result.scalar()

    def get_all_document_hashes(self) -> Dict[str, str]:
        return self._run(self.aget_all_document_hashes())

    async def aget_all_document_hashes(self) -> Dict[str, str]:
        """返回 {doc_hash: doc_id}（与KVDocumentStore语义一致）"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(LlamaDocstoreNode.doc_hash, LlamaDocstoreNode.node_id).where(
                    LlamaDocstoreNode.doc_hash.isnot(None)
                )
            )
            return {doc_hash: node_id for doc_hash, node_id in result}

    # ===== Ref Docs =====
    def get_all_ref_doc_info(self) -> Optional[Dict[str, RefDocInfo]]:
        return self._run(self.aget_all_ref_doc_info())

    async def aget_all_ref_doc_info(self) -> Optional[Dict[str, RefDocInfo]]:
        """单条SQL取全部 ref_doc_id -> node_ids（避免N+1查询）"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(LlamaDocstoreNode.ref_doc_id, LlamaDocstoreNode.node_id).where(
                    LlamaDocstoreNode.ref_doc_id.isnot(None)
                )
            )
            ref_map: Dict[str, RefDocInfo] = {}
            for ref_doc_id, node_id in result:
                if ref_doc_id not in ref_map:
                    ref_map[ref_doc_id] = RefDocInfo(node_ids=[], metadata={})
                ref_map[ref_doc_id].node_ids.append(node_id)
            return ref_map or None

    def get_ref_doc_info(self, ref_doc_id: str) -> Optional[RefDocInfo]:
        return self._run(self.aget_ref_doc_info(ref_doc_id))

    async def aget_ref_doc_info(self, ref_doc_id: str) -> Optional[RefDocInfo]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(LlamaDocstoreNode.node_id).where(
                    LlamaDocstoreNode.ref_doc_id == ref_doc_id
                )
            )
            node_ids = [row[0] for row in result]
        if not node_ids:
            return None
        return RefDocInfo(node_ids=node_ids, metadata={})

    def delete_ref_doc(self, ref_doc_id: str, raise_error: bool = True) -> None:
        self._run(self.adelete_ref_doc(ref_doc_id, raise_error))

    async def adelete_ref_doc(self, ref_doc_id: str, raise_error: bool = True) -> None:
        """删除ref_doc及其全部子节点（ref_doc_id匹配 或 节点自身id即ref_doc_id）"""
        async with self._session_factory() as session:
            result = await session.execute(
                delete(LlamaDocstoreNode).where(
                    (LlamaDocstoreNode.ref_doc_id == ref_doc_id)
                    | (LlamaDocstoreNode.node_id == ref_doc_id)
                )
            )
            await session.commit()
        if result.rowcount == 0 and raise_error:
            raise ValueError(f"ref_doc_id {ref_doc_id} not found.")
