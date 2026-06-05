import base64
import json
from dataclasses import dataclass
from urllib import error, parse, request

from app.config import get_settings


@dataclass(frozen=True)
class MessageResult:
    status: str
    provider_message_id: str | None = None
    detail: str = ""


class SmsService:
    def send_sms(self, to_phone: str, body: str) -> MessageResult:
        settings = get_settings()
        provider = settings.sms_provider.lower().strip()
        if provider == "stub":
            return MessageResult(
                status="sms_not_configured",
                detail="Set SMS_PROVIDER=twilio or SMS_PROVIDER=fast2sms with credentials to send booking confirmations.",
            )
        if provider == "twilio":
            missing = [
                name
                for name, value in {
                    "TWILIO_ACCOUNT_SID": settings.twilio_account_sid,
                    "TWILIO_AUTH_TOKEN": settings.twilio_auth_token,
                    "TWILIO_FROM_NUMBER": settings.twilio_from_number,
                }.items()
                if not value
            ]
            if missing:
                return MessageResult(status="sms_credentials_missing", detail=f"Missing: {', '.join(missing)}")

            return self._send_twilio_sms(
                settings.twilio_account_sid,
                settings.twilio_auth_token,
                settings.twilio_from_number,
                to_phone,
                body,
            )
        if provider == "fast2sms":
            missing = [
                name
                for name, value in {
                    "FAST2SMS_API_KEY": settings.fast2sms_api_key,
                }.items()
                if not value
            ]
            if missing:
                return MessageResult(status="sms_credentials_missing", detail=f"Missing: {', '.join(missing)}")

            return self._send_fast2sms_sms(
                api_key=settings.fast2sms_api_key,
                route=settings.fast2sms_route,
                language=settings.fast2sms_language,
                sender_id=settings.fast2sms_sender_id,
                to_phone=to_phone,
                body=body,
            )

        return MessageResult(
            status="sms_not_configured",
            detail="Unsupported SMS_PROVIDER. Use stub, twilio, or fast2sms.",
        )

    @staticmethod
    def _send_twilio_sms(
        account_sid: str,
        auth_token: str,
        from_phone: str,
        to_phone: str,
        body: str,
    ) -> MessageResult:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        payload = parse.urlencode({"From": from_phone, "To": to_phone, "Body": body}).encode()
        token = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
        twilio_request = request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with request.urlopen(twilio_request, timeout=10) as response:
                response_body = json.loads(response.read().decode())
        except error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            return MessageResult(status="sms_failed", detail=detail)
        except OSError as exc:
            return MessageResult(status="sms_failed", detail=str(exc))

        return MessageResult(status="sms_sent", provider_message_id=response_body.get("sid"), detail="SMS sent.")

    @staticmethod
    def _send_fast2sms_sms(
        api_key: str,
        route: str,
        language: str,
        sender_id: str | None,
        to_phone: str,
        body: str,
    ) -> MessageResult:
        url = "https://www.fast2sms.com/dev/bulkV2"
        digits_only = "".join(ch for ch in to_phone if ch.isdigit())
        if digits_only.startswith("91") and len(digits_only) > 10:
            digits_only = digits_only[-10:]
        if len(digits_only) != 10:
            return MessageResult(
                status="sms_invalid_recipient",
                detail="Recipient number must contain a valid 10-digit Indian mobile number.",
            )

        payload: dict[str, str | int] = {
            "route": route,
            "message": body,
            "language": language,
            "flash": 0,
            "numbers": digits_only,
        }
        if sender_id:
            payload["sender_id"] = sender_id

        fast2sms_request = request.Request(
            url,
            data=parse.urlencode(payload).encode(),
            headers={
                "authorization": api_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(fast2sms_request, timeout=10) as response:
                response_body = json.loads(response.read().decode())
        except error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            return MessageResult(status="sms_failed", detail=detail)
        except OSError as exc:
            return MessageResult(status="sms_failed", detail=str(exc))

        if not response_body.get("return", False):
            return MessageResult(
                status="sms_failed",
                detail=_stringify_fast2sms_message(response_body.get("message", "Fast2SMS rejected request.")),
            )

        request_id = None
        request_ids = response_body.get("request_id")
        if isinstance(request_ids, list) and request_ids:
            request_id = str(request_ids[0])
        elif isinstance(request_ids, str):
            request_id = request_ids

        return MessageResult(status="sms_sent", provider_message_id=request_id, detail="SMS sent.")


def _stringify_fast2sms_message(value: object) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value)
    return str(value)


sms_service = SmsService()
