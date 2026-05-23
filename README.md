# VaaniAI

VaaniAI is a multilingual AI healthcare receptionist MVP. It runs as a web-based voice agent that listens to a patient, understands symptoms or requested specialties, shows matching doctors and appointment slots, collects patient details, confirms the booking on screen, and sends an SMS confirmation after the appointment is created.

The current version is built for a browser experience instead of telephone routing. A patient opens the web app, Vaani greets them, the microphone starts automatically, and the backend handles the complete appointment workflow.

## What It Does

- Speaks to patients through a browser-based voice interface.
- Accepts English, Hindi, and Hinglish-style patient input.
- Understands either symptoms such as "chest pain" or direct specialties such as "cardiologist".
- Shows available doctor and slot options on screen.
- Keeps slot options visible until a slot is selected.
- Shows the selected doctor and appointment time after slot selection.
- Collects patient name, gender, age, and phone number.
- Shows a final booking review before confirming.
- Books the appointment only after confirmation.
- Sends the final booking SMS through Fast2SMS.
- Optionally creates a Google Calendar event for the booked slot.
- Stores appointments, transcripts, notifications, sessions, doctors, and slots in the database.

## Outcome

At the end of a successful flow:

1. The patient has selected a doctor and slot.
2. The patient has reviewed and confirmed their details.
3. The appointment is saved in the database.
4. The slot is locked so it cannot be reused.
5. The patient receives an SMS confirmation.
6. The UI shows a success state and then resets for a new session.
7. If enabled, the appointment is also added to Google Calendar.

## Architecture

```text
Patient Browser
     |
     | microphone audio
     v
FastAPI /voice/turn
     |
     | audio bytes
     v
ElevenLabs STT
     |
     | transcribed text
     v
Conversation Engine
     |
     | symptom/specialty detection
     | slot matching
     | patient detail collection
     | booking review
     v
Database
     |
     | confirmed booking
     +---------------------> Fast2SMS confirmation
     |
     +---------------------> optional Google Calendar event
     |
     | assistant reply
     v
ElevenLabs TTS
     |
     | generated audio URL
     v
Patient Browser UI
```

OpenRouter is used for conversational fallback and optional voice-agent reply polishing. The core booking decisions, slot validation, patient detail collection, and confirmation logic remain inside the backend state machine.

## Tech Stack

- Backend: FastAPI
- Database layer: SQLModel and SQLAlchemy
- Local database: SQLite
- Hosted database option: MySQL or another SQLAlchemy-compatible database
- Frontend: static HTML, CSS, and JavaScript served by FastAPI
- STT: ElevenLabs
- TTS: ElevenLabs
- LLM: OpenRouter
- SMS: Fast2SMS
- Optional calendar sync: Google Calendar API
- Tests: pytest

## Project Structure

```text
app/
  audio.py          ElevenLabs, Groq, Faster-Whisper, and TTS wrappers
  calendar.py       Optional Google Calendar sync
  config.py         Environment configuration
  database.py       Database engine and startup migrations
  intent.py         Intent, symptom, detail, phone, age, and slot parsing
  llm.py            OpenRouter integration
  main.py           FastAPI routes
  messaging.py      Fast2SMS and Twilio SMS wrappers
  models.py         SQLModel database models
  schemas.py        API request and response schemas
  security.py       API key, rate limit, and upload validation helpers
  services.py       Booking, session, dashboard, transcript, and state-machine logic

frontend/
  index.html        Web voice-agent screen
  styles.css        Premium black UI styling
  app.js            Browser microphone loop and UI state handling

scripts/
  seed_demo_data.py Demo doctors, symptoms, and slots

tests/
  test_api.py
  test_audio.py
  test_chat_flow.py
  test_intent.py
  test_messaging.py
```

## Main User Flow

```text
1. User opens /app
2. Vaani greets the user
3. Browser records speech automatically
4. Frontend sends audio to /voice/turn
5. Backend transcribes audio with ElevenLabs STT
6. Backend detects symptom or requested specialization
7. Backend returns matching doctor/slot options
8. User chooses a slot
9. Backend collects name, gender, age, and phone
10. Frontend shows booking review
11. User confirms
12. Backend creates appointment and locks slot
13. Fast2SMS sends confirmation SMS
14. Optional Google Calendar event is created
15. UI shows booking success and resets for a fresh session
```

## API Overview

Core app:

- `GET /` - service metadata
- `GET /health` - health and database check
- `GET /app` - browser voice-agent UI

Demo and data:

- `POST /demo/seed` - seed demo doctors and slots
- `POST /demo/reset-bookings` - clear test appointments and unlock slots
- `GET /doctors` - list doctors and symptoms
- `GET /available-slots` - list available slots, optionally by specialization

Conversation:

- `POST /session/start` - start a fresh web session
- `GET /session/{call_id}` - read current session state
- `POST /session/{call_id}/reset` - reset one session
- `POST /chat` - text-based conversation fallback
- `POST /voice/turn` - full voice turn: STT, chat, and optional TTS

Audio:

- `POST /transcribe` - transcribe uploaded audio
- `POST /tts` - generate speech for assistant text
- `POST /speech-to-speech` - optional ElevenLabs speech-to-speech conversion

Booking and operations:

- `POST /book-appointment` - direct booking endpoint
- `GET /dashboard/metrics` - booking and operational metrics
- `GET /dashboard/recent-bookings` - recent appointments
- `GET /transcripts` - stored conversation transcripts
- `GET /notifications` - SMS notification audit log

## Environment Setup

Create a local environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy the sample environment file:

```powershell
copy .env.example .env
```

For local stub testing, the default `.env.example` values are enough. For live testing, configure the providers below.

## Required Live Provider Configuration

### ElevenLabs

ElevenLabs is used for speech-to-text and text-to-speech.

```env
STT_PROVIDER=elevenlabs
TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
ELEVENLABS_FALLBACK_VOICE_ID=
ELEVENLABS_STT_MODEL=scribe_v2
ELEVENLABS_TTS_MODEL=eleven_multilingual_v2
ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128
```

### OpenRouter

OpenRouter is used for natural conversation fallback and optional receptionist-style reply polishing.

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openai/gpt-4o
VOICE_AGENT_POLISH_REPLIES=true
```

### Fast2SMS

Fast2SMS sends the final appointment confirmation.

```env
SMS_PROVIDER=fast2sms
FAST2SMS_API_KEY=...
FAST2SMS_ROUTE=q
FAST2SMS_LANGUAGE=english
FAST2SMS_SENDER_ID=
CLINIC_NAME="Pawani Medicals"
```

### Optional Google Calendar

Google Calendar sync is optional. When enabled, each confirmed booking creates a calendar event and stores the sync status on the appointment.

```env
CALENDAR_PROVIDER=google
GOOGLE_CALENDAR_ID=your-calendar-id@gmail.com
GOOGLE_CALENDAR_CREDENTIALS_FILE=D:\VaaniAI\secrets\google-calendar-service-account.json
```

Keep the service account JSON outside git. Share the target calendar with the service account email before testing.

## Database

The default database is local SQLite:

```env
DATABASE_URL=sqlite:///./vaaniai.db
```

For hosted deployment, use a persistent database:

```env
DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST:3306/vaaniai
```

The app includes startup migration logic for the current MVP schema, including doctor symptoms, session booking fields, calendar status fields, and MySQL-safe call state storage.

## Run Locally

Seed demo data:

```powershell
python scripts\seed_demo_data.py
```

Start the app:

```powershell
python -m uvicorn app.main:app --reload --port 8020
```

Open:

```text
http://127.0.0.1:8020/app
```

API docs:

```text
http://127.0.0.1:8020/docs
```

## Testing

Run the test suite:

```powershell
pytest -q
```

Expected current result:

```text
45 passed
```

Check frontend JavaScript syntax:

```powershell
node --check frontend\app.js
```

## Local Demo Checklist

Before showing the demo:

- Start the server on port `8020`.
- Open `/app`.
- Confirm Vaani speaks the greeting.
- Allow microphone permission.
- Say a symptom such as "I have knee pain" or a specialty such as "I need a cardiologist".
- Confirm doctor and slot cards stay visible until selection.
- Select a slot by speaking the slot time or slot number.
- Confirm the selected appointment panel appears.
- Give name, gender, age, and phone.
- Confirm the review panel stays visible until confirmation.
- Say confirm.
- Confirm success state appears.
- Confirm SMS is sent or logged.
- Confirm appointment is created in the database.

## Hosting Plan

For a hosted demo, deploy the FastAPI app and serve `/app` from the same backend.

Required hosted environment values:

```env
PUBLIC_BASE_URL=https://your-public-domain.example
DATABASE_URL=...
STT_PROVIDER=elevenlabs
TTS_PROVIDER=elevenlabs
LLM_PROVIDER=openrouter
SMS_PROVIDER=fast2sms
```

Recommended deployment sequence:

1. Push the repository to GitHub.
2. Choose a hosting provider such as Render, Railway, or Fly.io.
3. Add all environment variables in the hosting dashboard.
4. Use a persistent database instead of local SQLite.
5. Set the start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

6. Open `https://your-domain/app`.
7. Run one full booking with real ElevenLabs, OpenRouter, and Fast2SMS keys.

For temporary sharing from a local machine:

```powershell
python -m uvicorn app.main:app --reload --port 8020
ngrok http 8020
```

Then share:

```text
https://your-ngrok-domain/app
```

## Security Notes

Do not commit:

- `.env`
- API keys
- `vaaniai.db`
- generated audio files
- Google service account JSON files
- production call or patient data

The repository includes `.gitignore` rules for local secrets, generated audio, virtual environments, logs, and local databases.

For this MVP, production-grade authentication and distributed rate limiting are intentionally out of scope. The app includes optional API-key protection, upload validation, and simple local rate limiting as demo safeguards.

## Current Status

The backend, local web UI, voice turn orchestration, symptom/specialty matching, appointment booking flow, Fast2SMS integration, ElevenLabs STT/TTS integration, OpenRouter integration, optional Google Calendar sync, and automated tests are implemented.

Remaining work before public demo:

- Add real provider keys on the host.
- Configure hosted database and public URL.
- Run one complete hosted voice booking test.
- Verify SMS delivery in the hosted environment.
- Enable and verify Google Calendar sync only if required for the demo.
