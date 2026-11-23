"""Common Pydantic Schemas and Response Envelopes."""

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class StandardResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str
    details: Optional[dict] = None
