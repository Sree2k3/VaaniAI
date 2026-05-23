import json
from dataclasses import dataclass
from urllib import error, request

from app.config import get_settings


@dataclass(frozen=True)
class LlmResult:
    text: str
    status: str
    detail: str = ""


class LlmService:
    def generate_reply(self, user_text: str, context: str = "") -> LlmResult:
        settings = get_settings()
        provider = settings.llm_provider.lower().strip()
        if provider == "stub":
            return LlmResult(text="", status="llm_not_configured", detail="Set LLM_PROVIDER=openrouter.")
        if provider != "openrouter":
            return LlmResult(text="", status="llm_not_configured", detail="Unsupported LLM provider.")
        if not settings.openrouter_api_key:
            return LlmResult(text="", status="llm_credentials_missing", detail="Missing OPENROUTER_API_KEY.")

        prompt = self._build_prompt(user_text, context)
        return self._send_openrouter_request(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            prompt=prompt,
        )

    def polish_voice_reply(
        self,
        raw_reply: str,
        state: str,
        action: str | None = None,
        patient_text: str = "",
    ) -> LlmResult:
        settings = get_settings()
        provider = settings.llm_provider.lower().strip()
        if not settings.voice_agent_polish_replies:
            return LlmResult(text="", status="llm_not_configured", detail="Voice-agent polishing is disabled.")
        if provider != "openrouter":
            return LlmResult(text="", status="llm_not_configured", detail="Set LLM_PROVIDER=openrouter.")
        if not settings.openrouter_api_key:
            return LlmResult(text="", status="llm_credentials_missing", detail="Missing OPENROUTER_API_KEY.")

        prompt = self._build_voice_polish_prompt(raw_reply, state, action, patient_text)
        return self._send_openrouter_request(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            prompt=prompt,
            system_message=(
                "You are Vaani, a warm receptionist at Pawani Medicals. Rewrite assistant replies for fluent spoken "
                "delivery in English without changing facts, slots, booking details, names, phone numbers, or required next actions."
            ),
            temperature=0.35,
        )

    @staticmethod
    def _build_prompt(user_text: str, context: str) -> str:
        return (
            "You are Vaani, a warm and fluent receptionist working at Pawani Medicals. "
            "Ask what symptoms the patient is facing, guide them to the right doctor, and help with appointment booking. "
            "Keep replies short, natural, and suitable for spoken conversation. "
            "If the question is unrelated to clinic support, ask user to focus on appointment help.\n\n"
            f"Context:\n{context}\n\n"
            f"User:\n{user_text}"
        )

    @staticmethod
    def _build_voice_polish_prompt(raw_reply: str, state: str, action: str | None, patient_text: str) -> str:
        return (
            "Rewrite the backend reply as a natural voice-agent receptionist line.\n"
            "Rules:\n"
            "- Keep the same meaning and next action.\n"
            "- Keep the reply in English.\n"
            "- Keep patient names in English script exactly as provided by the backend.\n"
            "- Sound warm, human, and conversational, not like a form or script.\n"
            "- Use contractions where natural.\n"
            "- Acknowledge briefly when helpful, but do not over-apologize.\n"
            "- Ask only one question.\n"
            "- Do not diagnose or give medical advice.\n"
            "- Do not add new slots, doctors, dates, IDs, phone numbers, promises, or policies.\n"
            "- Keep it under 20 words unless the original contains a list.\n"
            "- Return only the rewritten line.\n\n"
            f"Conversation state: {state}\n"
            f"Action: {action or 'none'}\n"
            f"Patient just said: {patient_text}\n"
            f"Backend reply: {raw_reply}"
        )

    @staticmethod
    def _send_openrouter_request(
        api_key: str,
        model: str,
        prompt: str,
        system_message: str = "You are Vaani, a concise receptionist at Pawani Medicals.",
        temperature: float = 0.2,
    ) -> LlmResult:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        openrouter_request = request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(openrouter_request, timeout=15) as response:
                response_body = json.loads(response.read().decode())
        except error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            return LlmResult(text="", status="llm_failed", detail=detail)
        except OSError as exc:
            return LlmResult(text="", status="llm_failed", detail=str(exc))

        choices = response_body.get("choices") or []
        if not choices:
            return LlmResult(text="", status="llm_failed", detail="No response choices returned.")
        message = choices[0].get("message", {})
        text = (message.get("content") or "").strip()
        if not text:
            return LlmResult(text="", status="llm_failed", detail="Empty response from LLM.")
        return LlmResult(text=text, status="llm_generated")


llm_service = LlmService()
