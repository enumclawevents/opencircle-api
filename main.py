import os
print("ADMIN KEY SEEN BY SERVER:", os.getenv("OPENCIRCLE_ADMIN_KEY")
)
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from db import SessionLocal, engine, Base
from models import Event, Publisher
from schemas import EventCreate, EventOut, EventUpdate, PublisherCreate, PublisherOut

app = FastAPI(title="OpenCircle API")

Base.metadata.create_all(bind=engine)

def utcnow():
    return datetime.now(timezone.utc)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def normalize_city(city: str) -> str:
    return " ".join(city.strip().split())

def parse_allowed_cities(allowed_cities: str) -> set[str]:
    parts = [c.strip() for c in allowed_cities.split(",") if c.strip()]
    return {c.lower() for c in parts}

def require_admin_key(x_admin_key: Optional[str] = Header(None)):
    expected = os.getenv("OPENCIRCLE_ADMIN_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="Server admin key not configured")
    if x_admin_key != expected:
        raise HTTPException(status_code=401, detail="Invalid admin key")


def get_publisher_from_key(
    x_publisher_key: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Publisher:
    if not x_publisher_key:
        raise HTTPException(status_code=401, detail="Missing X-Publisher-Key")

    publisher = db.query(Publisher).filter(Publisher.api_key == x_publisher_key).first()
    if not publisher or not publisher.is_active:
        raise HTTPException(status_code=401, detail="Invalid publisher key")

    return publisher

@app.get("/")
def root():
    return {"ok": True, "name": "OpenCircle API"}

# -------------------------
# PUBLIC READ
# Only return published events by default
# -------------------------
@app.get("/events", response_model=List[EventOut])
def get_events(
    city: str = "Enumclaw",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    include_drafts: bool = Query(False),
    db: Session = Depends(get_db),
):
    city_norm = normalize_city(city)

    q = db.query(Event).filter(func.lower(Event.city) == func.lower(city_norm))

    # Public default is published only
    if not include_drafts:
        q = q.filter(Event.status == "published")

    return (
        q.order_by(Event.start_datetime.asc())
         .offset(offset)
         .limit(limit)
         .all()
    )

@app.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status != "published":
        # keep it simple: non-published is not publicly readable
        raise HTTPException(status_code=404, detail="Event not found")
    return event

# -------------------------
# ADMIN: manage publishers
# -------------------------
@app.post("/admin/publishers", response_model=PublisherOut, status_code=201, dependencies=[Depends(require_admin_key)])
def create_publisher(payload: PublisherCreate, db: Session = Depends(get_db)):
    cities = [normalize_city(c) for c in payload.allowed_cities]
    stored = ",".join(cities)

    if db.query(Publisher).filter(Publisher.name == payload.name.strip()).first():
        raise HTTPException(status_code=400, detail="Publisher name already exists")

    if db.query(Publisher).filter(Publisher.api_key == payload.api_key.strip()).first():
        raise HTTPException(status_code=400, detail="Publisher api_key already exists")

    pub = Publisher(
        name=payload.name.strip(),
        api_key=payload.api_key.strip(),
        allowed_cities=stored,
        is_active=payload.is_active,
    )
    db.add(pub)
    db.commit()
    db.refresh(pub)
    return pub

@app.get("/admin/publishers", response_model=List[PublisherOut], dependencies=[Depends(require_admin_key)])
def list_publishers(db: Session = Depends(get_db)):
    return db.query(Publisher).order_by(Publisher.id.asc()).all()

@app.patch("/admin/publishers/{publisher_id}/deactivate", response_model=PublisherOut, dependencies=[Depends(require_admin_key)])
def deactivate_publisher(publisher_id: int, db: Session = Depends(get_db)):
    pub = db.query(Publisher).filter(Publisher.id == publisher_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publisher not found")
    pub.is_active = False
    db.commit()
    db.refresh(pub)
    return pub

# -------------------------
# ADMIN: review + publish workflow
# -------------------------
@app.get("/admin/events", response_model=List[EventOut], dependencies=[Depends(require_admin_key)])
def admin_list_events(
    city: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Event)
    if city:
        city_norm = normalize_city(city)
        q = q.filter(func.lower(Event.city) == func.lower(city_norm))
    if status:
        q = q.filter(Event.status == status)

    return (
        q.order_by(Event.created_at.desc())
         .offset(offset)
         .limit(limit)
         .all()
    )

@app.patch("/admin/events/{event_id}/publish", response_model=EventOut, dependencies=[Depends(require_admin_key)])
def admin_publish_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    event.status = "published"
    event.updated_at = utcnow()
    db.commit()
    db.refresh(event)
    return event

@app.patch("/admin/events/{event_id}/unpublish", response_model=EventOut, dependencies=[Depends(require_admin_key)])
def admin_unpublish_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    event.status = "draft"
    event.updated_at = utcnow()
    db.commit()
    db.refresh(event)
    return event

# -------------------------
# PUBLISHER: create draft (cannot publish)
# -------------------------
@app.post("/events", response_model=EventOut, status_code=201)
def create_event(
    payload: EventCreate,
    publisher: Publisher = Depends(get_publisher_from_key),
    db: Session = Depends(get_db),
):
    if payload.end_datetime and payload.end_datetime < payload.start_datetime:
        raise HTTPException(status_code=400, detail="end_datetime cannot be before start_datetime")

    city_norm = normalize_city(payload.city)
    allowed = parse_allowed_cities(publisher.allowed_cities)
    if city_norm.lower() not in allowed:
        raise HTTPException(status_code=403, detail="Publisher not allowed to post to this city")

    now = utcnow()
    event = Event(
        city=city_norm,
        title=payload.title.strip(),
        description=(payload.description.strip() if payload.description else None),
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        location=(payload.location.strip() if payload.location else None),
        organizer=(payload.organizer.strip() if payload.organizer else None),
        source_url=(payload.source_url.strip() if payload.source_url else None),
        external_id=(payload.external_id.strip() if payload.external_id else None),
        status="draft",  # always draft on creation
        created_at=now,
        updated_at=now,
        publisher_id=publisher.id,
    )

    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate external_id for this publisher")
    db.refresh(event)
    return event

@app.patch("/events/{event_id}", response_model=EventOut)
def update_event(
    event_id: int,
    payload: EventUpdate,
    publisher: Publisher = Depends(get_publisher_from_key),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.publisher_id != publisher.id:
        raise HTTPException(status_code=403, detail="Not allowed to edit this event")

    data = payload.model_dump(exclude_unset=True)

    # Publisher cannot publish directly
    if "status" in data and data["status"] == "published":
        raise HTTPException(status_code=403, detail="Publish requires admin approval")

    # If city changes, validate allowed
    if "city" in data and isinstance(data["city"], str):
        new_city = normalize_city(data["city"])
        allowed = parse_allowed_cities(publisher.allowed_cities)
        if new_city.lower() not in allowed:
            raise HTTPException(status_code=403, detail="Publisher not allowed to move event to this city")
        data["city"] = new_city

    # Validate date ordering
    new_start = data.get("start_datetime", event.start_datetime)
    new_end = data.get("end_datetime", event.end_datetime)
    if new_end and new_start and new_end < new_start:
        raise HTTPException(status_code=400, detail="end_datetime cannot be before start_datetime")

    # Apply updates
    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(event, key, value)

    event.updated_at = utcnow()

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate external_id for this publisher")

    db.refresh(event)
    return event

@app.delete("/events/{event_id}", status_code=204)
def delete_event(
    event_id: int,
    publisher: Publisher = Depends(get_publisher_from_key),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.publisher_id != publisher.id:
        raise HTTPException(status_code=403, detail="Not allowed to delete this event")

    db.delete(event)
    db.commit()
    return None
