from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey,
    UniqueConstraint
)
from db import Base

class Publisher(Base):
    __tablename__ = "publishers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    api_key = Column(String, unique=True, nullable=False)
    allowed_cities = Column(String, nullable=False, default="")
    is_active = Column(Boolean, nullable=False, default=True)


class Event(Base):
    __tablename__ = "events"

    __table_args__ = (
        # Prevent duplicates from the same publisher/source
        UniqueConstraint("publisher_id", "external_id", name="uq_publisher_external_id"),
    )

    id = Column(Integer, primary_key=True, index=True)

    city = Column(String, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=True)

    location = Column(String, nullable=True)
    organizer = Column(String, nullable=True)

    # Workflow + metadata
    status = Column(String, nullable=False, default="draft")  # draft|published|archived
    source_url = Column(String, nullable=True)
    external_id = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    publisher_id = Column(Integer, ForeignKey("publishers.id"), nullable=True)
