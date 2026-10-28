"""Request and response models shared by the routers."""

from pydantic import BaseModel, Field

from rfp.services.jobs import ReviewStatus


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(description="Number of entries over all pages")
    limit: int
    offset: int


class LoginRequest(BaseModel):
    username: str
    password: str


class ReviewRequest(BaseModel):
    """What a reviewer changes. A new ``text`` without ``status`` marks the answer as edited."""

    text: str | None = Field(default=None, description="Corrected answer text")
    status: ReviewStatus | None = Field(default=None, description="New review status")
    note: str | None = Field(default=None, description="Comment for other reviewers")


class ReferenceResponse(BaseModel):
    doc_id: str = Field(description="Knowledge-base document holding the reviewed answer, REF-<id>")


class ErrorResponse(BaseModel):
    detail: str
