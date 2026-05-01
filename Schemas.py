from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any, Union

class QueryResult(BaseModel):
    query: str = Field(default="", description="搜索关键词")
    title: str = Field(default="", description="搜索结果标题")
    url: str = Field(default="", description="搜索结果链接")
    summary: str = Field(default="", description="搜索结果摘要")