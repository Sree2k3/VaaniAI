from pathlib import Path
import sys

from sqlalchemy import delete
from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine, init_db
from app.models import Doctor, DoctorAvailability, Slot
from app.services import (
    DEFAULT_MAX_PATIENTS_PER_AVAILABILITY,
    DEMO_AVAILABILITY_END_TIME,
    DEMO_SLOT_DATES,
    DEMO_SLOT_TIMES,
    reset_test_bookings,
    seed_demo_data,
)


def main() -> None:
    init_db()
    with Session(engine) as session:
        seed_demo_data(session)
        reset_test_bookings(session)
        session.exec(delete(DoctorAvailability))
        session.exec(delete(Slot))
        session.commit()

        doctors = session.exec(select(Doctor).where(Doctor.active == True).order_by(Doctor.id)).all()
        availability_count = 0
        for doctor in doctors:
            for slot_date in DEMO_SLOT_DATES:
                for slot_time in DEMO_SLOT_TIMES:
                    session.add(
                        DoctorAvailability(
                            doctor_id=doctor.id,
                            available_date=slot_date,
                            start_time=slot_time,
                            end_time=DEMO_AVAILABILITY_END_TIME,
                            max_patients=DEFAULT_MAX_PATIENTS_PER_AVAILABILITY,
                        )
                    )
                    availability_count += 1

        session.commit()

    print(
        "appointments=0, "
        f"availabilities_reset={availability_count}, "
        f"max_patients={DEFAULT_MAX_PATIENTS_PER_AVAILABILITY}, "
        "dates=2026-06-06,2026-06-07,2026-06-08,2026-06-09"
    )


if __name__ == "__main__":
    main()
