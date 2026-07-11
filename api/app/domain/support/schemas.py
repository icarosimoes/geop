from pydantic import BaseModel, Field


class SupportRequestCreate(BaseModel):
    contact_name: str = Field(min_length=1, max_length=160)
    contact_whatsapp: str = Field(min_length=1, max_length=30)
    message: str | None = Field(None, max_length=2000)


class SupportRequestCreated(BaseModel):
    id: int
    status: str
