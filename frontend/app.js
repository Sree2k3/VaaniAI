const state = {
  callId: `web-${crypto.randomUUID()}`,
  userPhone: "demo",
  language: "hi",
  audioStream: null,
  audioContext: null,
  analyser: null,
  mediaRecorder: null,
  chunks: [],
  recognition: null,
  interimTurn: null,
  lastRecognizedText: "",
  listening: false,
  recording: false,
  speaking: false,
  busy: false,
  unlocked: false,
  greetingStarted: false,
  greetingVoiceFinished: false,
  speechSeen: false,
  silenceStartedAt: 0,
  recordingStartedAt: 0,
  lastStopAt: 0,
  animationFrame: 0,
  lastSlotOptions: [],
  selectedSlot: null,
  bookingReview: null,
};

const els = {
  voiceOrb: document.getElementById("voiceOrb"),
  recordHint: document.getElementById("recordHint"),
  connectionStatus: document.getElementById("connectionStatus"),
  transcriptList: document.getElementById("transcriptList"),
  assistantLine: document.getElementById("assistantLine"),
  slotCards: document.getElementById("slotCards"),
  selectedSlotBox: document.getElementById("selectedSlotBox"),
  selectedSlotDetails: document.getElementById("selectedSlotDetails"),
  reviewBox: document.getElementById("reviewBox"),
  reviewGrid: document.getElementById("reviewGrid"),
  successBox: document.getElementById("successBox"),
  successText: document.getElementById("successText"),
  stateLabel: document.getElementById("stateLabel"),
  textInput: document.getElementById("textInput"),
  unlockNote: document.getElementById("unlockNote"),
};

const greeting = "Hello, I am Vaani from Pawani Medicals. How may I help you today? Please tell me your symptoms or the specialist you would like to see.";
const voiceThreshold = 0.055;
const silenceMs = 1400;
const minRecordingMs = 900;
const minAudioBytes = 1800;

function setStatus(label, tone = "") {
  els.connectionStatus.textContent = label;
  els.connectionStatus.className = `status-pill ${tone}`.trim();
}

function setOrbMode(mode) {
  els.voiceOrb.classList.remove("listening", "speaking", "processing", "idle");
  els.voiceOrb.classList.add(mode);
}

function describeTtsFailure(tts) {
  if (!tts) {
    return "No TTS audio returned.";
  }
  const detail = tts.detail ? ` ${tts.detail}` : "";
  return `ElevenLabs TTS failed: ${tts.status}.${detail}`;
}

function describeSttFailure(payload) {
  if (!payload) {
    return "No STT response returned.";
  }
  const detail = payload.stt_detail ? ` ${payload.stt_detail}` : "";
  return `ElevenLabs STT failed: ${payload.stt_status || "unknown"}.${detail}`;
}

function updateManualEntry(nextState = "") {
  const editableStates = new Set(["collect_name", "confirm_name", "collect_gender", "collect_age", "collect_phone", "review_booking"]);
  els.textInput.hidden = !editableStates.has(nextState);
  if (nextState === "collect_name" || nextState === "confirm_name") {
    els.textInput.placeholder = "Correct or spell the patient name, then press Enter";
  } else if (nextState === "review_booking") {
    els.textInput.placeholder = "Say or type confirm, no, or the corrected detail";
  } else {
    els.textInput.placeholder = "Type a correction and press Enter";
  }
}

function showUnlockHint(show) {
  els.unlockNote.hidden = !show;
}

function addTurn(speaker, text, pending = false) {
  if (speaker === "Assistant") {
    els.assistantLine.textContent = text;
  }
  const turn = document.createElement("article");
  turn.className = `turn ${speaker === "You" ? "user-turn" : "assistant-turn"}`;
  if (pending) {
    turn.dataset.pending = "true";
  }

  const label = document.createElement("span");
  label.textContent = speaker;
  const body = document.createElement("p");
  body.textContent = text;
  turn.append(label, body);
  els.transcriptList.appendChild(turn);
  els.transcriptList.scrollTop = els.transcriptList.scrollHeight;
  return turn;
}

function updatePendingTurn(text) {
  if (!text) {
    return;
  }
  if (!state.interimTurn) {
    state.interimTurn = addTurn("You", text, true);
    return;
  }
  state.interimTurn.querySelector("p").textContent = text;
}

function commitUserTurn(text) {
  if (state.interimTurn) {
    state.interimTurn.querySelector("p").textContent = text;
    state.interimTurn.removeAttribute("data-pending");
    state.interimTurn = null;
    return;
  }
  addTurn("You", text);
}

function clearPendingTurn() {
  if (state.interimTurn) {
    state.interimTurn.remove();
    state.interimTurn = null;
  }
}

function formatSlotTime(startTime) {
  return new Date(startTime).toLocaleString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function renderSlots(slotOptions = [], selectedSlot = null) {
  els.slotCards.innerHTML = "";
  if (selectedSlot) {
    const empty = document.createElement("p");
    empty.className = "empty-text";
    empty.textContent = "Slot selected. The chosen doctor and time are shown below.";
    els.slotCards.appendChild(empty);
    return;
  }

  if (!slotOptions.length) {
    const empty = document.createElement("p");
    empty.className = "empty-text";
    empty.textContent = "Doctor and slot options will appear here when Vaani finds a match.";
    els.slotCards.appendChild(empty);
    return;
  }

  slotOptions.forEach((slot) => {
    const card = document.createElement("article");
    card.className = "slot-card";

    const doctor = document.createElement("strong");
    doctor.textContent = slot.doctor_name;

    const spec = document.createElement("span");
    spec.textContent = slot.specialization.replace(/\b\w/g, (letter) => letter.toUpperCase());

    const time = document.createElement("span");
    time.textContent = formatSlotTime(slot.start_time);

    const code = document.createElement("code");
    code.textContent = `Say: slot ${slot.slot_id}`;

    card.append(doctor, spec, time, code);
    els.slotCards.appendChild(card);
  });
}

function renderSelectedSlot(slot) {
  if (!slot) {
    els.selectedSlotBox.hidden = true;
    els.selectedSlotDetails.innerHTML = "";
    return;
  }

  els.selectedSlotDetails.innerHTML = "";
  const card = document.createElement("article");
  card.className = "selected-slot-card";

  const doctor = document.createElement("strong");
  doctor.textContent = slot.doctor_name;

  const specialty = document.createElement("span");
  specialty.textContent = slot.specialization.replace(/\b\w/g, (letter) => letter.toUpperCase());

  const time = document.createElement("span");
  time.textContent = formatSlotTime(slot.start_time);

  const code = document.createElement("code");
  code.textContent = `Slot ${slot.slot_id}`;

  card.append(doctor, specialty, time, code);
  els.selectedSlotDetails.appendChild(card);
  els.selectedSlotBox.hidden = false;
}

function renderReview(review) {
  if (!review) {
    els.reviewBox.hidden = true;
    els.reviewGrid.innerHTML = "";
    return;
  }

  const rows = [
    ["Name", review.name],
    ["Gender", review.gender],
    ["Age", String(review.age)],
    ["Phone", review.phone],
    ["Doctor", review.doctor_name],
    ["Specialty", review.specialization],
    ["Time", review.slot_time],
  ];

  els.reviewGrid.innerHTML = "";
  rows.forEach(([label, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    els.reviewGrid.append(dt, dd);
  });
  els.reviewBox.hidden = false;
}

function syncBookingPanels(data = {}) {
  const nextState = data.next_state || data.state || "idle";
  const incomingSlots = data.slot_options || [];

  if (incomingSlots.length) {
    state.lastSlotOptions = incomingSlots;
  }
  if (data.selected_slot) {
    state.selectedSlot = data.selected_slot;
  }
  if (data.booking_review) {
    state.bookingReview = data.booking_review;
  } else if (!["review_booking", "confirm_booking", "booked"].includes(nextState)) {
    state.bookingReview = null;
  }
  if (["idle", "collect_specialization", "show_slots"].includes(nextState) && !data.selected_slot) {
    state.selectedSlot = null;
  }
  if (nextState === "idle") {
    state.lastSlotOptions = [];
  }

  renderSlots(state.lastSlotOptions, state.selectedSlot);
  renderSelectedSlot(state.selectedSlot);
  renderReview(state.bookingReview);
}

function renderSuccess(chat) {
  if (!chat || chat.next_state !== "booked") {
    els.successBox.hidden = true;
    return;
  }

  const smsText = chat.notification_status
    ? `Booking ID ${chat.appointment_id}. SMS status: ${chat.notification_status}.`
    : `Booking ID ${chat.appointment_id}.`;
  els.successText.textContent = smsText;
  els.successBox.hidden = false;
}

function clearVisibleBookingState() {
  state.lastSlotOptions = [];
  state.selectedSlot = null;
  state.bookingReview = null;
  renderSlots([]);
  renderSelectedSlot(null);
  renderReview(null);
  els.successBox.hidden = true;
  els.stateLabel.textContent = "idle";
  els.assistantLine.textContent = "Ready for the next patient.";
  updateManualEntry("idle");
}

async function startFreshSessionAfterBooking() {
  window.setTimeout(async () => {
    clearVisibleBookingState();
    state.callId = `web-${crypto.randomUUID()}`;
    state.userPhone = "demo";
    state.lastRecognizedText = "";
    clearPendingTurn();
    els.transcriptList.innerHTML = "";
    state.greetingStarted = false;
    state.greetingVoiceFinished = false;
    try {
      await startSession();
      speakAssistant("I'm ready for the next appointment. Please tell me your symptoms or the specialist you would like to see.", resumeListening, { addTranscript: false });
    } catch (error) {
      console.error(error);
      resumeListening();
    }
  }, 3200);
}

function getAudioMimeType() {
  const options = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/wav"];
  return options.find((type) => window.MediaRecorder?.isTypeSupported(type)) || "";
}

function getSpeechRecognition() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function startInterimRecognition() {
  const SpeechRecognition = getSpeechRecognition();
  if (!SpeechRecognition || state.recognition) {
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "hi-IN";
  recognition.onresult = (event) => {
    if (state.speaking || state.busy) {
      return;
    }
    let text = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      text += event.results[index][0].transcript;
    }
    const cleanText = text.trim();
    if (cleanText) {
      state.lastRecognizedText = cleanText;
      updatePendingTurn(cleanText);
    }
  };
  recognition.onerror = () => {};
  recognition.onend = () => {
    if (state.listening && !state.speaking && !state.busy && !state.recording) {
      window.setTimeout(() => {
        try {
          recognition.start();
        } catch (_error) {}
      }, 500);
    }
  };
  state.recognition = recognition;
  try {
    recognition.start();
  } catch (_error) {}
}

function stopInterimRecognition() {
  if (!state.recognition) {
    return;
  }
  try {
    state.recognition.stop();
  } catch (_error) {}
}

async function requestBackendTts(text) {
  const response = await fetch("/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      language: state.language,
    }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

function chooseVoice() {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  return (
    voices.find((voice) => voice.lang === "en-IN" && /female|woman|zira|heera|neural/i.test(voice.name)) ||
    voices.find((voice) => voice.lang === "en-IN") ||
    voices.find((voice) => voice.lang === "hi-IN" && /female|woman|zira|heera|neural/i.test(voice.name)) ||
    voices.find((voice) => voice.lang === "hi-IN") ||
    voices.find((voice) => /^en/i.test(voice.lang)) ||
    null
  );
}

function handleAssistantAudioFailure(message, afterSpeak = resumeListening) {
  setStatus("Voice setup issue", "error");
  els.recordHint.textContent = message;
  showUnlockHint(true);
  state.speaking = false;
  afterSpeak();
}

function speakAssistant(text, afterSpeak = resumeListening, options = {}) {
  const { addTranscript = true, skipBackendAudio = false } = options;
  els.assistantLine.textContent = text;
  if (addTranscript) {
    addTurn("Assistant", text);
  }

  if (!skipBackendAudio) {
    requestBackendTts(text)
      .then((tts) => {
        if (tts.status === "synthesized" && tts.audio_url) {
          playBackendAudio(tts, text, afterSpeak, { addTranscript: false });
          return;
        }
        setStatus("TTS failed", "error");
        handleAssistantAudioFailure(describeTtsFailure(tts), afterSpeak);
      })
      .catch((error) => {
        console.error(error);
        handleAssistantAudioFailure(
          `Could not reach backend TTS. ${error.message || "Check ElevenLabs settings and server logs."}`,
          afterSpeak,
        );
      });
    return;
  }

  if (!("speechSynthesis" in window)) {
    afterSpeak();
    return;
  }

  pauseListening();
  state.speaking = true;
  setStatus("Speaking");
  setOrbMode("speaking");
  els.recordHint.textContent = "Vaani is speaking";

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-IN";
  utterance.rate = 0.9;
  utterance.pitch = 1.02;
  const voice = chooseVoice();
  if (voice) {
    utterance.voice = voice;
  }
  utterance.onend = () => {
    state.speaking = false;
    state.unlocked = true;
    if (text === greeting) {
      state.greetingVoiceFinished = true;
    }
    showUnlockHint(false);
    afterSpeak();
  };
  utterance.onerror = () => {
    state.speaking = false;
    showUnlockHint(true);
    setStatus("Audio blocked", "error");
    els.recordHint.textContent = "Browser blocked speech playback. Click once and try again.";
    afterSpeak();
  };
  window.speechSynthesis.speak(utterance);
}

function playBackendAudio(tts, fallbackText, afterSpeak = resumeListening, options = {}) {
  const { addTranscript = true } = options;
  if (!tts || !tts.audio_url || tts.status !== "synthesized") {
    handleAssistantAudioFailure(describeTtsFailure(tts), afterSpeak);
    return;
  }

  if (addTranscript) {
    addTurn("Assistant", fallbackText);
  }
  pauseListening();
  state.speaking = true;
  setStatus("Speaking");
  setOrbMode("speaking");
  const audio = new Audio(tts.audio_url);
  audio.preload = "auto";
  audio.volume = 1;
  audio.onended = () => {
    state.speaking = false;
    state.unlocked = true;
    showUnlockHint(false);
    afterSpeak();
  };
  audio.onerror = () => {
    state.speaking = false;
    handleAssistantAudioFailure("Backend audio was generated but could not play. Click once and try again.", afterSpeak);
  };
  audio.play().catch(() => {
    state.speaking = false;
    handleAssistantAudioFailure("Browser blocked audio playback. Click once and try again.", afterSpeak);
  });
}

function applyVoiceTurn(payload) {
  if (payload.stt_text) {
    commitUserTurn(payload.stt_text);
  } else if (state.lastRecognizedText) {
    const fallbackText = state.lastRecognizedText;
    commitUserTurn(fallbackText);
    sendTextToBackend(fallbackText, { alreadyCommitted: true });
    return;
  } else {
    clearPendingTurn();
    addTurn("You", "No speech detected");
  }

  const chat = payload.chat;
  if (!chat) {
    const detail = describeSttFailure(payload);
    els.recordHint.textContent = detail;
    if (payload.stt_status === "no_speech_detected") {
      clearPendingTurn();
      setStatus("Listening");
      els.recordHint.textContent = "Listening automatically";
      window.setTimeout(resumeListening, 400);
      return;
    }
    speakAssistant("The speech service could not process that audio. Please check the voice configuration.");
    return;
  }

  els.stateLabel.textContent = chat.next_state || "idle";
  updateManualEntry(chat.next_state || "idle");
  syncBookingPanels(chat);
  renderSuccess(chat);
  const afterSpeak = chat.next_state === "booked" ? startFreshSessionAfterBooking : resumeListening;
  playBackendAudio(payload.tts, chat.reply, afterSpeak);
}

function applyTextChat(chat) {
  els.stateLabel.textContent = chat.next_state || "idle";
  updateManualEntry(chat.next_state || "idle");
  syncBookingPanels(chat);
  renderSuccess(chat);
  const afterSpeak = chat.next_state === "booked" ? startFreshSessionAfterBooking : resumeListening;
  speakAssistant(chat.reply, afterSpeak);
}

function pauseListening() {
  state.listening = false;
  stopInterimRecognition();
}

function resumeListening() {
  if (!state.audioStream) {
    return;
  }
  state.listening = true;
  setStatus("Listening");
  setOrbMode("listening");
  els.recordHint.textContent = "Listening automatically";
  startInterimRecognition();
}

function startRecorder() {
  if (state.recording || state.busy || state.speaking || !state.audioStream) {
    return;
  }

  const mimeType = getAudioMimeType();
  const recorder = new MediaRecorder(state.audioStream, mimeType ? { mimeType } : undefined);
  state.mediaRecorder = recorder;
  state.chunks = [];
  state.lastRecognizedText = "";
  state.recording = true;
  state.speechSeen = true;
  state.silenceStartedAt = 0;
  state.recordingStartedAt = performance.now();

  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) {
      state.chunks.push(event.data);
    }
  };
  recorder.onstop = () => {
    state.recording = false;
    state.lastStopAt = performance.now();
    const blob = new Blob(state.chunks, { type: mimeType || "audio/webm" });
    sendVoiceTurn(blob, mimeType || "audio/webm");
  };
  recorder.start();
  setStatus("Recording");
  setOrbMode("listening");
}

function stopRecorder() {
  if (!state.mediaRecorder || state.mediaRecorder.state === "inactive") {
    return;
  }
  state.mediaRecorder.stop();
}

async function sendVoiceTurn(blob, mimeType) {
  if (!blob.size) {
    resumeListening();
    return;
  }
  if (blob.size < minAudioBytes) {
    clearPendingTurn();
    resumeListening();
    return;
  }

  state.busy = true;
  pauseListening();
  setStatus("Thinking");
  setOrbMode("processing");
  els.recordHint.textContent = "Processing your request";

  const form = new FormData();
  const extension = mimeType.includes("mp4") ? "m4a" : mimeType.includes("wav") ? "wav" : "webm";
  form.append("audio", blob, `voice-turn.${extension}`);

  try {
    const params = new URLSearchParams({
      call_id: state.callId,
      user_phone: state.userPhone,
      language: state.language,
      synthesize_reply: "true",
    });
    const response = await fetch(`/voice/turn?${params.toString()}`, {
      method: "POST",
      body: form,
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const payload = await response.json();
    state.busy = false;
    applyVoiceTurn(payload);
  } catch (error) {
    state.busy = false;
    console.error(error);
    if (state.lastRecognizedText) {
      const fallbackText = state.lastRecognizedText;
      commitUserTurn(fallbackText);
      sendTextToBackend(fallbackText, { alreadyCommitted: true });
      return;
    }
    els.recordHint.textContent = error.message || "Voice turn request failed.";
    speakAssistant("I could not process that audio. Please check microphone access and the voice service settings.");
  }
}

function monitorAudioLevel() {
  if (!state.analyser) {
    return;
  }

  const data = new Uint8Array(state.analyser.fftSize);
  state.analyser.getByteTimeDomainData(data);
  let sum = 0;
  for (const value of data) {
    const normalized = (value - 128) / 128;
    sum += normalized * normalized;
  }
  const volume = Math.sqrt(sum / data.length);
  const now = performance.now();

  if (state.listening && !state.speaking && !state.busy) {
    if (volume > voiceThreshold && now - state.lastStopAt > 900) {
      startRecorder();
    }
    if (state.recording) {
      if (volume <= voiceThreshold) {
        state.silenceStartedAt = state.silenceStartedAt || now;
      } else {
        state.silenceStartedAt = 0;
      }

      const recordedFor = now - state.recordingStartedAt;
      if (state.silenceStartedAt && now - state.silenceStartedAt > silenceMs && recordedFor > minRecordingMs) {
        stopRecorder();
      }
    }
  }

  state.animationFrame = requestAnimationFrame(monitorAudioLevel);
}

async function resumeAudioContext() {
  if (state.audioContext && state.audioContext.state === "suspended") {
    try {
      await state.audioContext.resume();
    } catch (_error) {
      showUnlockHint(true);
    }
  }
}

async function initMicrophone() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    setStatus("Type mode");
    setOrbMode("idle");
    els.recordHint.textContent = "Microphone recording is unavailable. Type below and press Enter.";
    return;
  }

  state.audioStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  state.audioContext = new (window.AudioContext || window.webkitAudioContext)();
  await resumeAudioContext();
  const source = state.audioContext.createMediaStreamSource(state.audioStream);
  state.analyser = state.audioContext.createAnalyser();
  state.analyser.fftSize = 1024;
  source.connect(state.analyser);
  resumeListening();
  monitorAudioLevel();
}

async function sendTextToBackend(message, options = {}) {
  const { alreadyCommitted = false } = options;
  if (!message.trim() || state.busy) {
    return;
  }

  pauseListening();
  state.busy = true;
  setStatus("Thinking");
  setOrbMode("processing");
  els.recordHint.textContent = "Checking appointment details";

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        call_id: state.callId,
        user_phone: state.userPhone,
        message,
        language: state.language,
      }),
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const chat = await response.json();
    state.busy = false;
    applyTextChat(chat);
  } catch (error) {
    state.busy = false;
    console.error(error);
    if (!alreadyCommitted) {
      commitUserTurn(message);
    }
    speakAssistant("I could not connect to the appointment system. Please try again.");
  }
}

async function startSession() {
  setStatus("Starting");
  setOrbMode("processing");
  const response = await fetch("/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ call_id: state.callId, user_phone: state.userPhone, language: state.language, fresh: true }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const session = await response.json();
  els.stateLabel.textContent = session.state;
  updateManualEntry(session.state || "idle");
  syncBookingPanels(session);
}

async function unlockVoiceExperience() {
  if (state.unlocked) {
    return;
  }
  state.unlocked = true;
  showUnlockHint(false);
  await resumeAudioContext();
  if (state.speaking) {
    return;
  }
  if (!state.greetingStarted) {
    state.greetingStarted = true;
    speakAssistant(greeting);
  } else if (!state.greetingVoiceFinished) {
    speakAssistant(greeting, resumeListening, { addTranscript: false });
  } else {
    resumeListening();
  }
}

function bindAudioUnlock() {
  const unlock = () => {
    unlockVoiceExperience().catch((error) => {
      console.error(error);
      showUnlockHint(true);
    });
  };
  window.addEventListener("pointerdown", unlock, { once: true });
  window.addEventListener("keydown", unlock, { once: true });
}

function bindTypedFallback() {
  els.textInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    const message = els.textInput.value.trim();
    els.textInput.value = "";
    if (message) {
      commitUserTurn(message);
      sendTextToBackend(message, { alreadyCommitted: true });
    }
  });
}

async function boot() {
  bindAudioUnlock();
  bindTypedFallback();
  try {
    await startSession();
    await initMicrophone();
    if (navigator.userActivation?.hasBeenActive) {
      await unlockVoiceExperience();
    } else {
      pauseListening();
      setStatus("Tap to start");
      setOrbMode("idle");
      els.recordHint.textContent = "Click anywhere once to start Vaani";
      els.assistantLine.textContent = "Vaani is ready.";
      showUnlockHint(true);
    }
  } catch (error) {
    console.error(error);
    setStatus("Mic blocked", "error");
    setOrbMode("idle");
    showUnlockHint(true);
    els.textInput.hidden = false;
    addTurn("Assistant", "Microphone permission is blocked. Type your request below and press Enter.");
  }
}

if ("speechSynthesis" in window) {
  window.speechSynthesis.onvoiceschanged = () => {};
}

boot();
