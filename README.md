# VaaniAI Backend

VaaniAI is a multilingual AI healthcare receptionist MVP. This backend now targets a web-interactive voice agent flow (not telephony-first): audio upload -> STT -> conversation engine -> optional TTS -> booking + SMS confirmation.

## MVP Status

Backend completion for the agreed demo MVP is approximately 98-99%.

Completed backend:

- Browser voice-agent backend flow using `/voice/turn`
- Text fallback using `/chat`
- ElevenLabs STT provider support
- ElevenLabs TTS provider support
- Optional ElevenLabs speech-to-speech endpoint support
- Legacy Groq STT provider support remains available
- OpenRouter LLM fallback/inquiry support
- Optional OpenRouter voice-agent reply polishing for smoother receptionist transitions
- Fast2SMS booking confirmation support
- Doctor/specialization discovery
- Slot selection and slot locking
- Patient intake: name, gender, age, phone
- On-screen booking review payload
- Confirm-before-booking flow
- Appointment, transcript, notification, dashboard, and session APIs
- Optional Google Calendar appointment sync
- SQLite/MySQL-compatible startup schema migration
- Demo-safe API key option, simple local rate limiting, and audio upload validation
- Static frontend served from `/app`
- Premium voice-agent UI served from `/app`
- Automated tests passing: `pytest -q` -> 45 passed

Remaining for demo MVP:

- Live provider testing with real ElevenLabs, OpenRouter, and Fast2SMS keys
- Deployment/hosting configuration when a public demo link is needed
- MCP-based hosting/integration layer, if the final deployment path requires it

Not required for this demo MVP:

- Production-grade authentication
- Persistent/distributed rate limiting
- Telephony/call routing

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\seed_demo_data.py
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for API testing.
Open `http://127.0.0.1:8000/app` for the web voice UI.

## Current Backend Scope

- `GET /health`
- `POST /demo/seed`
- `GET /doctors`
- `GET /available-slots`
- `POST /chat`
- `POST /session/start`
- `GET /session/{call_id}`
- `POST /session/{call_id}/reset`
- `POST /book-appointment`
- `GET /dashboard/metrics`
- `GET /dashboard/recent-bookings`
- `GET /transcripts`
- `GET /notifications`
- `POST /transcribe` ElevenLabs/Groq/Faster-Whisper wrapper with optional transcript persistence and chat handoff
- `POST /voice/turn` unified voice turn orchestration: STT + chat + optional TTS
- `POST /tts` ElevenLabs/XTTS-backed speech generation
- `POST /speech-to-speech` ElevenLabs speech-to-speech conversion

## Recommended Frontend Flow

The first frontend implementation is available at `/app`.

Current UI behavior:

- Black background voice interface
- Centered live-agent signal with automatic listening/speaking/processing animation
- Vaani greets the patient automatically
- Automatic silence detection records patient speech and sends audio through `/voice/turn`
- ElevenLabs/backend STT is the target real transcription path during provider testing
- Text fallback input for browsers without microphone support, submitted with Enter
- Doctor/slot cards from `chat.slot_options`
- Selected appointment card remains visible after slot selection
- Booking review panel from `chat.booking_review`
- Review stays visible until the user confirms or corrects details
- Green success state only after `next_state=booked`
- Visible booking state clears and a fresh idle session starts automatically after confirmation
- Patient-facing transcript is hidden; backend transcript logging remains available through `/transcripts`
- No visible control buttons in the main interaction

Use the automatic browser voice loop for the main interaction:

1. Frontend starts a session with `POST /session/start`.
2. Vaani speaks the opening greeting.
3. Browser listens automatically and records until silence is detected.
4. Recorded audio is sent to `POST /voice/turn`.
5. Frontend speaks the assistant reply using backend TTS audio when available, otherwise browser speech synthesis.
6. Frontend shows doctor/slot cards, selected slot, review screen, and final green tick.
7. Frontend can rehydrate state with `GET /session/{call_id}` after refresh.

## Interactive Booking Flow (Current)

Conversation state machine for appointment booking:

1. User asks for doctor/symptom support.
2. Backend returns available slot options.
3. Backend collects verbal details in this order:
   - name
   - gender
   - age
   - phone
4. Backend returns `booking_review` for on-screen confirmation.
5. User confirms -> slot is booked -> SMS confirmation is sent/logged.

## Booking Confirmation SMS

Booking confirmations call an SMS service after `/chat` or `/book-appointment` creates a confirmed appointment. The default `SMS_PROVIDER=stub` does not send real messages, but it logs the attempt in `/notifications` so local demos and tests are deterministic. The current target provider is Fast2SMS.

To send real SMS messages, configure one provider.

Fast2SMS:

```env
SMS_PROVIDER=fast2sms
FAST2SMS_API_KEY=...
FAST2SMS_ROUTE=q
FAST2SMS_LANGUAGE=english
FAST2SMS_SENDER_ID=
CLINIC_NAME="Pawani Medicals"
```

Twilio remains a legacy optional provider if needed later:

```env
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+1...
```

## Speech-to-Text Setup

Copy `.env.example` to `.env` and change only the providers you want to enable.

Local Faster-Whisper STT does not require an API key and works in the current Python 3.12 environment:

```powershell
pip install -r requirements-audio.txt
```

Then set:

```env
STT_PROVIDER=faster_whisper
STT_MODEL_SIZE=small
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
```

ElevenLabs STT is the target provider for the current MVP:

```env
STT_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=...
ELEVENLABS_STT_MODEL=scribe_v2
```

Groq STT is still available as a legacy fallback:

```env
STT_PROVIDER=groq
GROQ_API_KEY=...
GROQ_STT_MODEL=whisper-large-v3-turbo
```

Use `/transcribe` with multipart form data:

- `audio`: uploaded audio file.
- `call_id`: optional call/session id. When present, successful transcription is stored in transcripts.
- `user_phone`: optional user key, defaults to `demo`.
- `language`: fallback language when STT cannot detect one.
- `auto_chat`: set `true` to immediately pass the transcribed text through the booking chat engine.

The response includes the transcribed `text`, detected `language`, STT `status`, and an optional `chat` response when `auto_chat=true`.

## LLM Setup (OpenRouter)

Conversation fallback/inquiry responses use OpenRouter. The backend can also ask OpenRouter to polish safe assistant prompts into smoother receptionist-style voice lines while keeping booking decisions, slot validation, and SMS logic inside VaaniAI.

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openai/gpt-4o
VOICE_AGENT_POLISH_REPLIES=true
```

The polishing layer is intentionally not used for slot lists, booking review details, booking IDs, phone numbers, or final confirmation data.

## Google Calendar Setup

Google Calendar sync is optional. When enabled, each confirmed booking creates a calendar event and stores the sync status on the appointment.

Install dependencies from the main requirements file:

```powershell
pip install -r requirements.txt
```

Then set:

```env
CALENDAR_PROVIDER=google
GOOGLE_CALENDAR_ID=your-calendar-id@gmail.com
GOOGLE_CALENDAR_CREDENTIALS_FILE=D:\VaaniAI\secrets\google-calendar-service-account.json
```

Keep the service account JSON outside git. Share the target Google Calendar with the service account email before testing.

## Text-to-Speech Setup

ElevenLabs TTS is the target provider for Vaani's spoken assistant replies:

```env
TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
ELEVENLABS_TTS_MODEL=eleven_multilingual_v2
ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128
```

Optional ElevenLabs speech-to-speech conversion uses the same API key and voice id:

```env
ELEVENLABS_STS_MODEL=eleven_multilingual_sts_v2
```

Local XTTS TTS remains available, but Coqui `TTS` currently needs Python 3.10 or 3.11. Install it in a separate compatible virtual environment:

```powershell
py -3.11 -m venv .venv-tts
.\.venv-tts\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-tts.txt
```

Then set:

```env
TTS_PROVIDER=xtts
TTS_SPEAKER_WAV=D:\VaaniAI\voice_samples\doctor.wav
```

`GEMINI_API_KEY` is only needed when the LLM response layer is added. `VAPI_API_KEY` and `VAPI_ASSISTANT_ID` are only needed when phone-call integration is added.

## Demo Provider Testing Checklist

Before frontend testing, confirm `.env` contains:

```env
STT_PROVIDER=elevenlabs
TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
ELEVENLABS_STT_MODEL=scribe_v2
ELEVENLABS_TTS_MODEL=eleven_multilingual_v2
ELEVENLABS_STS_MODEL=eleven_multilingual_sts_v2
ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128

LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openai/gpt-4o
VOICE_AGENT_POLISH_REPLIES=true

SMS_PROVIDER=fast2sms
FAST2SMS_API_KEY=...
FAST2SMS_ROUTE=q
FAST2SMS_LANGUAGE=english
FAST2SMS_SENDER_ID=
CLINIC_NAME="Pawani Medicals"

# Optional calendar sync
CALENDAR_PROVIDER=disabled
GOOGLE_CALENDAR_ID=
GOOGLE_CALENDAR_CREDENTIALS_FILE=
```

Run:

```powershell
pytest -q
python -m uvicorn app.main:app --reload
```

Then test one full flow:

`microphone audio -> /voice/turn -> ElevenLabs STT -> booking flow/OpenRouter fallback -> ElevenLabs TTS -> DB booking -> Fast2SMS confirmation -> frontend success state`.

## Hosting Readiness

For a public demo, deploy the FastAPI app and serve `/app` from the same backend. Required environment values on the host:

```env
PUBLIC_BASE_URL=https://your-public-domain.example
DATABASE_URL=...
STT_PROVIDER=elevenlabs
TTS_PROVIDER=elevenlabs
LLM_PROVIDER=openrouter
SMS_PROVIDER=fast2sms
```

Pre-host checklist:

- Run `pytest -q`.
- Start locally with `python -m uvicorn app.main:app --reload --port 8020`.
- Complete one booking from `http://127.0.0.1:8020/app`.
- Confirm ElevenLabs audio is heard from the browser.
- Confirm Fast2SMS sends or logs the final confirmation.
- If calendar sync is enabled, confirm `calendar_status=calendar_synced` on the appointment.
- Use a tunnel such as `ngrok http 8020` for temporary friend testing before final hosting.

The backend and frontend are ready for local and tunnel-based demo testing. Final hosting mainly needs provider keys, public base URL, persistent database choice, and deployment target configuration.
