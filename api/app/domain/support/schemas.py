from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Priority = Literal["BAIXA", "MEDIA", "ALTA"]


class SupportRequestCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=160)
    priority: Priority = "MEDIA"
    contact_name: str = Field(min_length=1, max_length=160)
    contact_whatsapp: str = Field(min_length=1, max_length=30)
    message: str | None = Field(None, max_length=2000)


class SupportRequestCreated(BaseModel):
    id: int
    status: str


class SupportRequestOut(BaseModel):
    id: int
    subject: str | None
    priority: str
    contact_name: str
    contact_whatsapp: str
    message: str | None
    status: str
    response_message: str | None
    created_at: datetime
    updated_at: datetime
