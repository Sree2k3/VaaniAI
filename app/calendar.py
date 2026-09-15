from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models import Appointment, Doctor, DoctorAvailability, Slot, User


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
        slot: Slot | DoctorAvailability,
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
        if isinstance(slot, DoctorAvailability):
            start_time, end_time = self._next_availability_window(slot)
        else:
            start_time = slot.start_time
            end_time = slot.end_time

        event = {
            "summary": f"{settings.clinic_name}: {user.name or 'Patient'} with {doctor.name}",
            "description": (
                f"Booking ID: {appointment.id}\n"
                f"Patient: {user.name or 'Patient'}\n"
                f"Phone: {patient_phone or user.phone}\n"
                f"Doctor: {doctor.name}\n"
                f"Specialization: {doctor.specialization}"
            ),
            "start": {"dateTime": start_time.isoformat(), "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "Asia/Kolkata"},
        }
        created = service.events().insert(calendarId=settings.google_calendar_id, body=event).execute()
        return CalendarResult(status="calendar_synced", event_id=created.get("id"), detail="Google Calendar event created.")

    @staticmethod
    def _next_availability_window(slot: DoctorAvailability) -> tuple[datetime, datetime]:
        """Return the next local calendar occurrence for a recurring daily availability."""
        local_timezone = ZoneInfo("Asia/Kolkata")
        now = datetime.now(local_timezone)
        start_time = datetime.combine(now.date(), slot.start_time, tzinfo=local_timezone)
        end_time = datetime.combine(now.date(), slot.end_time, tzinfo=local_timezone)
        if end_time <= start_time:
            end_time += timedelta(days=1)
        if start_time <= now:
            start_time += timedelta(days=1)
            end_time += timedelta(days=1)
        return start_time, end_time


calendar_service = CalendarService()
