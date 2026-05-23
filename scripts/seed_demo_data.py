import sys
from pathlib import Path

from sqlmodel import Session

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import engine, init_db
from app.services import seed_demo_data


def main() -> None:
    init_db()
    with Session(engine) as session:
        seed_demo_data(session)
    print("Seeded demo doctors, slots, users, calls, transcripts, appointments, and notifications.")


if __name__ == "__main__":
    main()
