from datetime import datetime, timezone
from db import Base, engine, SessionLocal
from models import Event, Publisher

def utcnow():
    return datetime.now(timezone.utc)

def run_seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Publisher).first():
            print("Database already has data. Skipping seed.")
            return

        pub = Publisher(
            name="EnumclawEvents",
            api_key="enumclawevents-demo-key-123456",
            allowed_cities="Enumclaw",
            is_active=True
        )
        db.add(pub)
        db.commit()
        db.refresh(pub)

        now = utcnow()
        event = Event(
            city="Enumclaw",
            title="OpenCircle Launch Meetup",
            description="Submitted by publisher; waiting on admin publish.",
            start_datetime=datetime.fromisoformat("2026-01-25T18:00:00"),
            end_datetime=datetime.fromisoformat("2026-01-25T20:00:00"),
            location="Enumclaw, WA",
            organizer="OpenCircle",
            status="draft",
            source_url="https://example.com/event",
            external_id="example-001",
            created_at=now,
            updated_at=now,
            publisher_id=pub.id,
        )
        db.add(event)
        db.commit()

        print("Seed complete.")
        print("Demo publisher key:", pub.api_key)
        print("Draft event created (needs admin publish).")
    finally:
        db.close()

if __name__ == "__main__":
    run()
