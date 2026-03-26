# Atlas Lingua with Deepgram :smirk: :sparkles:


If you're like me, learning a languag  requires ***brutal*** repetition, reiteration, and slow pronounciation. I created Atlas Lingua to do just this: take my time, practice my pronounciation, and utilize ***Deepgram's STT/TTS/multi-language/topic detection/and summarization capabilities*** . 


<img width="1478" height="788" alt="Screenshot 2026-03-26 at 11 03 17 AM" src="https://github.com/user-attachments/assets/dee21419-4087-48e9-a4ba-221ae236f0a6" />

<img width="1464" height="787" alt="Screenshot 2026-03-26 at 11 04 43 AM" src="https://github.com/user-attachments/assets/82322203-3ad6-420c-858c-4a98ec128b39" />

# Atlas Lingua Demo

Atlas Lingua Demo is a turn-based interactive language tutor built with **FastAPI**, a lightweight browser frontend, **Deepgram** speech/language APIs, and **OpenAI** for tutor/translation generation.

The application lets a user choose a target language, speak in English, and receive:
- an English speech-to-text transcription
- a translated version of what they said in the selected target language
- a tutor response that continues the conversation
- text-to-speech playback for both the translated learner utterance and the tutor reply
- end-of-session summarization and topic detection

The current implementation is optimized for **demo reliability** rather than full production streaming. Instead of maintaining a continuous live audio stream, the app records a single turn in the browser, uploads that recording to the backend, processes it, and returns a completed result.

---

## What this application does

At a high level, Atlas Lingua Demo demonstrates a multilingual tutoring loop:

1. The user selects a target language.
2. The user records a spoken English turn.
3. The app transcribes the recorded audio into English text.
4. The app generates:
   - the translated learner utterance in the target language
   - a tutor reply in the target language
   - an English hint / note for the learner
5. The app synthesizes spoken audio for the target-language text.
6. The user can continue the conversation turn by turn.
7. When the conversation ends, the app can summarize the session and detect key topics.

This makes the project a compact demo of:
- speech-to-text
- LLM-driven tutoring/translation
- text-to-speech
- transcript intelligence

---

## Quickstart

### 1. Run locally in mock mode

No API keys are required for your first run.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python run.py
```

### Core features

- **Language selection**
  - Choose from supported target languages mapped to Deepgram Aura voices.
  Current target languages:
   - English (`en`)
   - Spanish (`es`)
   - German (`de`)
   - French (`fr`)
   - Dutch (`nl`)
   - Italian (`it`)
   - Japanese (`ja`)

- **Turn-based voice interaction**
  - Record one learner turn at a time from the browser.

- **Speech-to-text transcription**
  - English audio is transcribed into English text.

- **LLM tutoring / translation**
  - The learner utterance is translated into the target language.
  - A short tutor response is generated to continue the conversation.

- **Text-to-speech playback**
  - The app generates playable audio for:
    - the translated learner utterance
    - the tutor response

- **Session summarization**
  - Generate a summary of the completed conversation.

- **Topic detection**
  - Extract the most important topics discussed in the session.

- **Mock mode**
  - Supports a mock/demo mode for testing UI and backend behavior without live API calls.

---

### System architecture
<img width="1779" height="326" alt="mermaid-diagram" src="https://github.com/user-attachments/assets/af8e295f-9164-4b24-917f-92972c32d2b4" />

### Frontend
A lightweight browser interface built from:
- server-rendered HTML template
- custom JavaScript
- custom CSS

The frontend is responsible for:
- language selection
- starting a session
- recording audio in the browser
- uploading recorded turns to the backend
- rendering returned text/audio
- triggering summary/topic actions

### Backend
A FastAPI application is responsible for:
- session creation and storage
- receiving recorded audio turns
- orchestrating the transcription/tutor/TTS pipeline
- managing session history
- generating end-of-session summary/topic analysis

### External services
The project uses:
- **Deepgram**
  - prerecorded speech-to-text
  - text-to-speech
  - summarization
  - topic detection
- **OpenAI**
  - target-language tutoring/translation generation

---

### End-to-end workflow

This is the current runtime workflow from start to finish.

### 1. User opens the app
The user loads the web interface in the browser.

### 2. User creates a session
The frontend calls the backend to create a new session with:
- selected target language
- difficulty level
- initial session metadata

### 3. User records a spoken English turn
The browser uses `MediaRecorder` to capture one full utterance.

### 4. Frontend uploads the recorded audio turn
The browser sends the audio file to the backend using a standard HTTP request.

### 5. Backend performs speech-to-text
The backend sends the recorded audio bytes to Deepgram prerecorded STT.

**Current model usage**
- Deepgram **Nova-3** is used for prerecorded transcription.

### 6. Backend generates tutoring content
The English transcript is sent to the tutor provider, which currently uses OpenAI to generate:
- the translated learner utterance
- the tutor reply in the selected target language
- an English hint
- optional teaching note / vocabulary items

### 7. Backend performs text-to-speech
The backend sends:
- the translated learner utterance
- the tutor reply

to Deepgram TTS for audio generation.

**Current model usage**
- Deepgram **Aura** voice models are used for TTS.

### 8. Backend returns the completed turn
The backend sends the frontend a completed turn payload containing:
- learner English transcript
- translated learner text
- tutor reply text
- audio asset references / payload-backed files
- teacher note / vocabulary metadata

### 9. Frontend renders the turn
The browser updates the interface so the user can:
- read the translated learner utterance
- read the tutor response
- play pronunciation audio
- continue the conversation

### 10. User ends the session
When the conversation is complete, the user ends the session.

### 11. Backend performs transcript intelligence
The app uses the accumulated English transcript and sends it to Deepgram Text Intelligence for:
- summarization
- topic detection

### 12. Frontend displays summary and topics
The user sees:
- a conversation summary
- top detected topics

---

### Why the app uses request/response APIs instead of live WebSocket streaming

Although the project contains a streaming-oriented code path, the primary implementation uses **record → upload → process → return**.

This was chosen because it is:
- simpler
- easier to debug
- more reliable for a demo
- well aligned with a turn-based tutoring UX

The app is currently optimized around complete recorded turns rather than continuous streaming audio.

---

### File structure

```text
atlas_lingua_demo/
├── run.py
├── pyproject.toml
├── .env.example
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   └── routes.py
│   ├── models/
│   │   └── domain.py
│   ├── services/
│   │   ├── conversation_orchestrator.py
│   │   └── providers/
│   │       ├── base.py
│   │       ├── deepgram.py
│   │       ├── openai_tutor.py
│   │       └── mock.py
│   ├── storage/
│   │   └── session_store.py
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── css/
│       │   └── styles.css
│       ├── js/
│       │   └── app.js
│       └── img/
│           ├── cartographer-1.png
│           └── cartographer-2.png
└── tests/
```

# In the future, I plan on extending this project by adding: 
- true streaming speech interaction with Flux
- pronunciation scoring 
- adaptive tutoring difficulty
- persistent database-backed session storage
- richer vocabulary/grammar feedback
- production deployment hardening
