from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from sqlalchemy import delete
from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine, init_db
from app.models import Doctor, Slot
from app.services import DEMO_SLOT_TIMES, reset_test_bookings, seed_demo_data


def main() -> None:
    init_db()
    with Session(engine) as session:
        seed_demo_data(session)
        reset_test_bookings(session)
        session.exec(delete(Slot))
        session.commit()

        doctors = session.exec(select(Doctor).where(Doctor.active == True).order_by(Doctor.id)).all()
        slot_dates = [
            datetime(2026, 6, 6, tzinfo=timezone.utc).date(),
            datetime(2026, 6, 7, tzinfo=timezone.utc).date(),
        ]
        slot_count = 0
        for doctor in doctors:
            for slot_date in slot_dates:
                for slot_time in DEMO_SLOT_TIMES:
                    start_time = datetime.combine(slot_date, slot_time, tzinfo=timezone.utc)
                    session.add(
                        Slot(
                            doctor_id=doctor.id,
                            start_time=start_time,
                            end_time=start_time + timedelta(minutes=30),
                            is_booked=False,
                        )
                    )
                    slot_count += 1

        session.commit()

    print(f"appointments=0, slots_reset={slot_count}, dates=2026-06-06,2026-06-07")


if __name__ == "__main__":
    main()
