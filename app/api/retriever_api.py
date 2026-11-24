import logging

from fastapi import APIRouter

from common.response import ResponseObject
from modules.retriever import service as retrieve_service
from modules.retriever.schema import RetrievalRequest

api = APIRouter(prefix="/retrieval")

log = logging.getLogger(__name__)


@api.post("/search")
async def retrieval(request: RetrievalRequest):
    log.info(f"检索请求: question={request.question}, dataset_ids={request.dataset_ids}, page={request.page}")
    data = await retrieve_service.retrieval(request)
    return ResponseObject(data=data)
