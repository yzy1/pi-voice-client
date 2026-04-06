# Pi Voice Client

Raspberry Pi voice client for a RAG + Ollama chatbot system.

## What This Does

The Raspberry Pi acts as a voice I/O terminal:
- Listens via USB microphone
- Converts speech to text using Vosk (local, offline)
- Sends text to a Windows server running FastAPI + Ollama + ChromaDB (RAG)
- Receives the answer
- Speaks the answer using Piper TTS

The Pi does NOT run an LLM. All heavy processing stays on the server.

## Architecture

Raspberry Pi Windows Server ┌──────────────┐ ┌─────────────────────┐ │ USB Mic │ │ FastAPI + Uvicorn │ │ → Vosk (STT) │ ── HTTP ──► │ ChromaDB (RAG) │ │ │ │ Ollama (llama3.1:8b) │ │ USB Speaker │ ◄── HTTP ── │ │ │ ← Piper(TTS) │ └─────────────────────┘ └──────────────┘


## Hardware

- Raspberry Pi 5 (4GB+)
- USB mic + speaker (P10S combo device)
- Windows PC running the FastAPI server

## Setup

See `SETUP_GUIDE.md` for detailed step-by-step instructions.

### Quick Start

1. Clone this repo to your Pi
2. Download models (not included in repo due to size):
   ```bash
   # Vosk model
   cd ~/voice-client
   wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
   unzip vosk-model-small-en-us-0.15.zip

   # Piper TTS
   wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz
   tar -xzf piper_linux_aarch64.tar.gz
   cd piper
   wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
   wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
Create virtual environment and install dependencies:

bash
cd ~/voice-client
python3 -m venv.venv
source.venv/bin/activate
pip install vosk sounddevice requests numpy
Start the server on your Windows PC:

bash
uvicorn main:app --host 0.0.0.0 --port 8080
Run the client on the Pi:

bash
# Voice mode
python voice_client.py

# Text mode
python voice_client.py --text
USB Audio Device Quirk (P10S)
The P10S USB device only supports stereo 48000 Hz. See SETUP_GUIDE.md for details.

Configuration
Edit the top of voice_client.py to change:

SERVER_URL — your Windows PC IP and port
VOSK_MODEL_PATH — path to Vosk model
PIPER_BINARY — path to Piper executable
PIPER_VOICE — path to Piper voice model
