# System Overview for AI
## RAG + Ollama + Voice Interaction System (Windows Server + Raspberry Pi Client)

---

## 1. Purpose of the System

This system is a local, end-to-end question-answering application that supports
text and voice input, document retrieval (RAG), local large language model
inference via Ollama, and speech synthesis.

The system has two components:
- A Windows server that handles RAG, LLM inference, and the web UI
- A Raspberry Pi client that acts as a voice I/O terminal

It is intended for museum guides, exhibitions, research demos, or offline
knowledge assistants.

---

## 2. Architecture

┌─────────────────────┐              ┌──────────────────────────┐
│   Raspberry Pi 5    │              │   Windows Server         │
│                     │              │                          │
│  🎤 USB Mic (P10S)  │              │   FastAPI + Uvicorn      │
│  → Vosk (STT)       │    HTTP      │   ChromaDB (RAG)         │
│  → Send text ───────┼─────────────►│   Ollama (llama3.1:8b)   │
│                     │              │   SentenceTransformer    │
│  🔊 USB Speaker     │◄─────────────┼── Response text          │
│  ← Piper (TTS)      │              │                          │
│  ← ffmpeg (stereo)  │              │   Also serves browser UI │
└─────────────────────┘              └──────────────────────────┘

The Pi does NOT run an LLM, RAG, or any heavy processing.
The Pi only handles: mic input → STT → HTTP request → TTS → speaker output.

---

## 3. GitHub Repository

URL: https://github.com/yzy1/pi-voice-client
Branch: main

Repository structure:
pi-voice-client/
├── client/                      Frontend (HTML + JS, served by FastAPI)
│   ├── asr_vosk.js
│   ├── chat.js
│   ├── index.html
│   ├── main.js
│   ├── pcm-player.worklet.js
│   ├── pcm-worklet.js
│   └── tts_stream.js
├── rag_docs/                    Knowledge base documents (Guanyin sculpture)
│   ├── Seated Guanyin _ The Art Institute of Chicago.txt
│   ├── Seeking Balance_ Material and Meaning in a Polychrome Guanyin _ The Art Institute of Chicago.txt
│   └── Uncovering the Many Faces of Guanyin _ The Art Institute of Chicago.txt
├── server/                      Windows server code
│   ├── agent_base.py           Abstract agent interface
│   ├── agent_factory.py        Selects agent based on AGENT_KIND env var
│   ├── agent_local.py          Simple local text-only agent
│   ├── agent_openai.py         OpenAI-based agent (optional)
│   ├── img.png
│   ├── main.py                 FastAPI application entry point
│   ├── rag_main_code.py        RAG + Ollama implementation
│   ├── requirements.txt        Python dependencies
│   ├── stt_vosk.py             Speech-to-text logic using Vosk
│   └── tts_piper.py            Text-to-speech using Piper
├──.gitignore
├── README.md
├── RUN.md                       Original execution instructions
├── SETUP_GUIDE.md               Pi setup steps 1-3 detailed guide
├── SYSTEM_OVERVIEW_FOR_AI.md    This file
└── voice_client.py              Pi client script

---

## 4. Windows Server Details

### 4.1 Machine Info
- User: YY Lab
- OS: Windows
- Project path: C:\Users\YY Lab\Documents\RAG_Zhiyuan\rag_exhibition-main\
- Git repo clone: C:\Users\YY Lab\Documents\pi-voice-client\

### 4.2 Core Technologies
- Backend framework: FastAPI
- ASGI server: Uvicorn
- Local LLM runtime: Ollama
- LLM model: llama3.1:8b
- RAG vector database: ChromaDB
- Embedding model: sentence-transformers/all-MiniLM-L6-v2
- Speech-to-text (ASR): Vosk
- Text-to-speech (TTS): Piper (optional, unstable on Windows)
- Configuration: python-dotenv

### 4.3 Server Configuration (.env file)
Located at: C:\Users\YY Lab\Documents\RAG_Zhiyuan\rag_exhibition-main\server\.env

AGENT_KIND=rag_ollama
OLLAMA_MODEL=llama3.1:8b
OLLAMA_URL=http://127.0.0.1:11434/api/generate
RAG_DOC_DIR=absolute_path_to_rag_docs
RAG_DB_PATH=absolute_path_to_chroma_db

### 4.4 Server Startup
cd "C:\Users\YY Lab\Documents\RAG_Zhiyuan\rag_exhibition-main\server".venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8080

IMPORTANT: Must use --host 0.0.0.0 (not 127.0.0.1) so the Pi can connect.

### 4.5 Server API Endpoints Used by Pi Client
- POST /agent/reply — Send text query, receive text reply
  Request:  {"text": "user question", "system": "optional system prompt"}
  Response: {"reply": "answer text"}
- POST /tts — Send text, receive WAV audio
  Request:  {"text": "text to speak", "voice": "optional voice model"}
  Response: audio/wav bytes
- GET /health — Health check, returns "ok"

### 4.6 Other Server Endpoints (used by browser UI)
- GET / — Serves the browser frontend (index.html)
- WebSocket /ws/asr — Real-time ASR via browser mic
- POST /agent/tts — Agent reply + TTS combined
- POST /tts/stream — Streaming TTS (PCM)
- POST /agent/tts/stream — Agent reply + streaming TTS

### 4.7 Agent Architecture
The agent_factory module reads AGENT_KIND from.env and instantiates the
appropriate agent. Supported modes:
- local (simple text agent)
- openai (OpenAI API agent)
- rag_ollama (RAG + local Ollama LLM — current mode)

### 4.8 RAG + Ollama Flow
1. User submits a query (text or speech)
2. Query text is embedded using SentenceTransformer (all-MiniLM-L6-v2)
3. ChromaDB retrieves the most relevant document chunks
4. Retrieved content is injected into a prompt
5. Prompt is sent to Ollama's LLM endpoint
6. Generated text is returned to the user

### 4.9 Network
- Wi-Fi IP: 192.168.68.XXX (changes — check with ipconfig each session)
- Last known IPs: 192.168.68.104, 192.168.68.103
- Port: 8080
- The Pi client must update SERVER_URL in voice_client.py if the IP changes

---

## 5. Raspberry Pi Client Details

### 5.1 Machine Info
- Hostname: PanagaPI
- User: admin
- OS: Raspberry Pi OS (Linux, ARM64)
- Model: Raspberry Pi 5, 4GB RAM
- Project path: /home/admin/voice-client/

### 5.2 Pi Folder Structure
~/voice-client/
├──.venv/                              Python virtual environment
├── vosk-model-small-en-us-0.15/        Vosk STT model (~40MB)
├── piper/                              Piper TTS
│   ├── piper                           Piper binary (ARM64 Linux)
│   ├── en_US-lessac-medium.onnx        Voice model
│   ├── en_US-lessac-medium.onnx.json   Voice model config
│   └── (other piper support files)
└── voice_client.py                     Main client script

### 5.3 Pi Technologies
- Speech-to-text: Vosk (vosk-model-small-en-us-0.15, offline)
- Text-to-speech: Piper (en_US-lessac-medium voice, offline)
- Audio conversion: ffmpeg (mono→stereo, 22050Hz→48000Hz)
- HTTP client: Python requests library
- Audio capture: Python sounddevice library
- Python packages: vosk, sounddevice, requests, numpy

### 5.4 Pi Client Startup
cd ~/voice-client
source.venv/bin/activate
python voice_client.py          # Voice mode (mic + speaker)
python voice_client.py --text   # Text mode (type questions)

### 5.5 Pi Client Configuration (top of voice_client.py)
SERVER_URL = "http://192.168.68.XXX:8080"   # Must match Windows IP
VOSK_MODEL_PATH = "~/voice-client/vosk-model-small-en-us-0.15"
PIPER_BINARY = "~/voice-client/piper/piper"
PIPER_VOICE = "~/voice-client/piper/en_US-lessac-medium.onnx"
MIC_SAMPLE_RATE = 48000
MIC_CHANNELS = 2
MIC_DEVICE = "hw:2,0"
SPEAKER_DEVICE = "hw:2,0"
VOSK_SAMPLE_RATE = 16000

### 5.6 Pi Client Flow
Voice mode:
1. Mic captures audio (stereo, 48000Hz, S16_LE)
2. Audio converted to mono 16000Hz for Vosk
3. Vosk transcribes speech to text
4. Text sent via HTTP POST to Windows server /agent/reply
5. Server returns answer text
6. Piper generates mono WAV (22050Hz)
7. ffmpeg converts to stereo 48000Hz
8. aplay plays through USB speaker

Text mode:
1. User types question
2. Steps 4-8 same as above

### 5.7 System prompt sent with each request
"Keep your answers concise and under 3 sentences. You are a voice assistant —
your responses will be spoken aloud."

---

## 6. USB Audio Device Quirk — CRITICAL

The P10S USB audio device (card 2, hw:2,0) has strict hardware constraints:

CAPTURE (Microphone):
- Format: S16_LE only
- Sample Rate: 48000 Hz only
- Channels: 2 (Stereo) only
- Mono recording FAILS with: "Channels count non available"

PLAYBACK (Speaker):
- Channels: Stereo only
- Mono playback FAILS with: "Channels count non available"
- Sample Rate: 48000 Hz preferred

CONSEQUENCE:
- Vosk needs mono 16000Hz → script downsamples from stereo 48000Hz
- Piper outputs mono 22050Hz → ffmpeg converts to stereo 48000Hz before playback
- All arecord commands must use: -f S16_LE -r 48000 -c 2
- All audio played must be stereo

Verify device detection:
  arecord -l    (should show card 2: P10S)
  aplay -l      (should show card 2: P10S)

---

## 7. Known Issues and Notes

- Windows server IP changes between sessions (DHCP). Check with ipconfig
  and update SERVER_URL in voice_client.py if needed.
- Piper TTS is unstable on Windows but works well on Pi (Linux).
- The aplay timeout is set to 180 seconds for long answers.
- The virtual environment must be activated every new terminal session.
- The.venv, models, and chroma_db are NOT in the git repo (too large).
  They must be set up locally following SETUP_GUIDE.md.

---

## 8. Git Workflow

From Windows:
  cd "C:\Users\YY Lab\Documents\pi-voice-client"
  git add.
  git commit -m "description of changes"
  git push

From Pi:
  cd ~/voice-client
  git add.
  git commit -m "description of changes"
  git push

GitHub authentication requires a Personal Access Token (not password).
Token must have "repo" scope.

---

## 9. Startup Procedure (Quick Reference)

1. WINDOWS: Start server
   cd "C:\Users\YY Lab\Documents\RAG_Zhiyuan\rag_exhibition-main\server".venv\Scripts\activate
   uvicorn main:app --host 0.0.0.0 --port 8080

2. WINDOWS: Check IP (new terminal)
   ipconfig
   (note the IPv4 address under Wi-Fi)

3. PI: Update IP if changed
   nano ~/voice-client/voice_client.py
   (Ctrl+W → SERVER_URL → update IP → Ctrl+O → Ctrl+X)

4. PI: Start client
   cd ~/voice-client
   source.venv/bin/activate
   python voice_client.py

---

## 10. User Details

- GitHub: yzy1
- Email: yangdaoy@gmail.com
- University: PSU (yzy1@psu.edu)
- Experience level: New to Linux, Raspberry Pi, and GitHub
- Prefers step-by-step instructions with explanations
- Common issue: missing spaces between commands (e.g., "source.venv" not "source.venv")