-- VaaniAI appointment availability/token migration.
-- Apply this to existing databases before reseeding demo data.

CREATE TABLE IF NOT EXISTS doctoravailability (
    id INTEGER PRIMARY KEY,
    doctor_id INTEGER NOT NULL,
    available_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    max_patients INTEGER NOT NULL DEFAULT 50,
    FOREIGN KEY (doctor_id) REFERENCES doctor(id),
    UNIQUE (doctor_id, available_date, start_time)
);

CREATE INDEX IF NOT EXISTS ix_doctoravailability_doctor_id
    ON doctoravailability (doctor_id);

CREATE INDEX IF NOT EXISTS ix_doctoravailability_available_date
    ON doctoravailability (available_date);

ALTER TABLE appointment ADD COLUMN availability_id INTEGER;
ALTER TABLE appointment ADD COLUMN token_number INTEGER;

CREATE UNIQUE INDEX IF NOT EXISTS uq_availability_token
    ON appointment (availability_id, token_number);

-- MySQL cleanup for databases created before DoctorAvailability.
-- Run these only if the named constraints/indexes exist in your schema.
-- ALTER TABLE calllog DROP FOREIGN KEY calllog_ibfk_3;
-- ALTER TABLE appointment DROP FOREIGN KEY appointment_ibfk_3;
-- DROP INDEX ix_appointment_slot_id ON appointment;
-- ALTER TABLE appointment MODIFY COLUMN slot_id INTEGER NULL;
