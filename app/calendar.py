from dataclasses import dataclass

from app.config import get_settings
from app.models import Appointment, Doctor, Slot, User


@dataclass(frozen=True)
class CalendarResult:
    status: str
    event_id: str | None = None
    detail: str = ""


class CalendarService:
    def create_appointment_event(
        self,
        appointment: Appointment,
        user: User,
        doctor: Doctor,
        slot: Slot,
        patient_phone: str | None = None,
    ) -> CalendarResult:
        settings = get_settings()
        if settings.calendar_provider.lower() not in {"google", "google_calendar"}:
            return CalendarResult(status="calendar_disabled", detail="Calendar sync is disabled.")
        if not settings.google_calendar_id or not settings.google_calendar_credentials_file:
            return CalendarResult(status="calendar_not_configured", detail="Google Calendar credentials are missing.")

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError:
            return CalendarResult(
                status="calendar_dependency_missing",
                detail="Install google-api-python-client and google-auth to enable Google Calendar sync.",
            )

        credentials = service_account.Credentials.from_service_account_file(
            settings.google_calendar_credentials_file,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        event = {
            "summary": f"{settings.clinic_name}: {user.name or 'Patient'} with {doctor.name}",
            "description": (
                f"Booking ID: {appointment.id}\n"
                f"Patient: {user.name or 'Patient'}\n"
                f"Phone: {patient_phone or user.phone}\n"
                f"Doctor: {doctor.name}\n"
                f"Specialization: {doctor.specialization}"
            ),
            "start": {"dateTime": slot.start_time.isoformat(), "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": slot.end_time.isoformat(), "timeZone": "Asia/Kolkata"},
        }
        created = service.events().insert(calendarId=settings.google_calendar_id, body=event).execute()
        return CalendarResult(status="calendar_synced", event_id=created.get("id"), detail="Google Calendar event created.")


calendar_service = CalendarService()
