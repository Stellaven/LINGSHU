from typing import Optional, Any

from pydantic import BaseModel, Field
from datetime import datetime


class ResponseObject(BaseModel):
    """统一成功响应格式"""
    success: bool = True
    code: int = 0
    data: Optional[Any] = None
    message: Optional[str] = None
    timestamp: str = Field(default_factory=lambda : datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
