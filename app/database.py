from collections.abc import Generator

from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine, text

from app.config import get_settings


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    apply_schema_migrations()


def apply_schema_migrations() -> None:
    migrations = {
        "doctor": {
            "symptoms": "JSON",
        },
        "appointment": {
            "availability_id": "INTEGER",
            "token_number": "INTEGER",
            "calendar_event_id": "VARCHAR(255)",
            "calendar_status": "VARCHAR(255)",
        },
        "user": {
            "gender": "VARCHAR(255)",
            "age": "INTEGER",
        },
        "calllog": {
            "selected_specialization": "VARCHAR(255)",
            "patient_gender": "VARCHAR(255)",
            "patient_age": "INTEGER",
            "patient_phone": "VARCHAR(255)",
        },
    }

    inspector = inspect(engine)
    preparer = engine.dialect.identifier_preparer
    with Session(engine) as session:
        for table_name, columns in migrations.items():
            if not inspector.has_table(table_name):
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            quoted_table = preparer.quote(table_name)
            for column_name, column_type in columns.items():
                if column_name in existing_columns:
                    continue
                quoted_column = preparer.quote(column_name)
                statement = f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {column_type}"
                if engine.dialect.name == "mysql" and table_name == "doctor" and column_name == "symptoms":
                    statement = f"{statement} AFTER specialization"
                session.exec(text(statement))
        session.commit()

    if engine.dialect.name == "mysql" and inspector.has_table("calllog"):
        make_mysql_call_state_text()
        remove_mysql_legacy_slot_constraints()

    if engine.dialect.name == "sqlite" and inspector.has_table("user"):
        remove_sqlite_user_phone_unique_index()


def make_mysql_call_state_text() -> None:
    with Session(engine) as session:
        session.exec(
            text(
                """
                ALTER TABLE calllog
                MODIFY COLUMN current_state VARCHAR(64) NOT NULL DEFAULT 'idle'
                """
            )
        )
        session.commit()


def remove_mysql_legacy_slot_constraints() -> None:
    inspector = inspect(engine)
    with Session(engine) as session:
        if inspector.has_table("calllog"):
            for foreign_key in inspector.get_foreign_keys("calllog"):
                if foreign_key.get("constrained_columns") == ["selected_slot_id"] and foreign_key.get("name"):
                    session.exec(text(f"ALTER TABLE calllog DROP FOREIGN KEY {foreign_key['name']}"))

        if inspector.has_table("appointment"):
            for foreign_key in inspector.get_foreign_keys("appointment"):
                if foreign_key.get("constrained_columns") == ["slot_id"] and foreign_key.get("name"):
                    session.exec(text(f"ALTER TABLE appointment DROP FOREIGN KEY {foreign_key['name']}"))

            for index in inspector.get_indexes("appointment"):
                if index.get("unique") and index.get("column_names") == ["slot_id"] and index.get("name"):
                    session.exec(text(f"DROP INDEX {index['name']} ON appointment"))

            session.exec(text("ALTER TABLE appointment MODIFY COLUMN slot_id INTEGER NULL"))
        session.commit()


def remove_sqlite_user_phone_unique_index() -> None:
    with Session(engine) as session:
        indexes = session.exec(text("PRAGMA index_list('user')")).all()
        for index in indexes:
            index_name = index[1]
            is_unique = bool(index[2])
            if not is_unique:
                continue
            index_columns = session.exec(text(f"PRAGMA index_info('{index_name}')")).all()
            column_names = [column[2] for column in index_columns]
            if column_names != ["phone"]:
                continue
            session.exec(text("ALTER TABLE user RENAME TO user_old"))
            SQLModel.metadata.tables["user"].create(engine)
            session.exec(
                text(
                    """
                    INSERT INTO user (
                        id, name, phone, gender, age, language_preference,
                        preferred_doctor_id, last_appointment_id, created_at
                    )
                    SELECT
                        id, name, phone, gender, age, language_preference,
                        preferred_doctor_id, last_appointment_id, created_at
                    FROM user_old
                    """
                )
            )
            session.exec(text("DROP TABLE user_old"))
            session.commit()
            return


apply_sqlite_migrations = apply_schema_migrations


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
