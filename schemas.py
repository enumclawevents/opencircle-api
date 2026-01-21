from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field

EventStatus = Literal["draft", "published", "archived"]

class EventCreate(BaseModel):
    city: str = Field(..., min_length=1, max_length=80)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None

    start_datetime: datetime
    end_datetime: Optional[datetime] = None

    location: Optional[str] = None
    organizer: Optional[str] = None

    source_url: Optional[str] = None
    external_id: Optional[str] = None


class EventUpdate(BaseModel):
    city: Optional[str] = Field(None, min_length=1, max_length=80)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None

    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None

    location: Optional[str] = None
    organizer: Optional[str] = None

    source_url: Optional[str] = None
    external_id: Optional[str] = None

    # Publishers may only set draft/archived; admin can set published too (enforced in main.py)
    status: Optional[EventStatus] = None


from pydantic import BaseModel

class PublisherCreate(BaseModel):
    name: str
    city: str | None = None

class PublisherOut(BaseModel):
    id: int
    name: str
    city: str | None = None
    api_key: str

    class Config:
        from_attributes = True


class EventOut(BaseModel):
    id: int
    city: str
    title: str
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    location: Optional[str] = None
    organizer: Optional[str] = None

    status: EventStatus
    source_url: Optional[str] = None
    external_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    publisher_id: Optional[int] = None

    class Config:
        from_attributes = True


class PublisherCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    allowed_cities: List[str] = Field(default_factory=list)
    is_active: bool = True

class PublisherOut(BaseModel):
    id: int
    name: str
    api_key: str
    allowed_cities: List[str]
    is_active: bool

    class Config:
        from_attributes = True
