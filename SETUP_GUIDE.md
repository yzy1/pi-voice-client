# Raspberry Pi Voice Client — Setup Guide
## Steps 1–3: Environment, Vosk STT, and Piper TTS

---

## Overview

This guide covers the initial setup of a Raspberry Pi as a **voice I/O terminal** that:
- Captures speech via a USB microphone
- Converts speech to text using Vosk (STT)
- Sends text to a remote FastAPI server for processing
- Receives response text and speaks it aloud using Piper (TTS)

The Raspberry Pi does **not** run an LLM or RAG system. It acts as a lightweight
frontend device. All heavy processing (Ollama, ChromaDB, embeddings) stays on the
Windows server.

---

## Architecture

┌─────────────────────┐         ┌──────────────────────────┐
│   Raspberry Pi      │         │   Windows Server         │
│                     │         │                          │
│  🎤 USB Mic         │         │   FastAPI + Uvicorn      │
│  → Vosk (STT)       │  HTTP   │   ChromaDB (RAG)         │
│  → Send text ───────┼────────►│   Ollama (llama3.1:8b)   │
│                     │         │   Embedding model        │
│  🔊 USB Speaker     │◄────────┼── Response text          │
│  ← Piper (TTS)      │         │                          │
└─────────────────────┘         └──────────────────────────┘

---

## Hardware

| Item | Details |
|---|---|
| Raspberry Pi | Pi 5, 4GB+ RAM |
| Microphone | USB (P10S combo device) |
| Speaker | USB (P10S combo device) |
| Power Supply | Official Pi 5 USB-C 27W PSU |
| MicroSD | 32GB+ Class A2 |

---

## USB Audio Device Quirk

The P10S USB audio device has fixed hardware parameters:

**Capture (Microphone):**
- Format: S16_LE (Signed 16-bit Little Endian)
- Sample Rate: 48000 Hz only
- Channels: 2 (Stereo only)

**Playback (Speaker):**
- Channels: Stereo only (mono audio will fail)
- Sample Rate: 48000 Hz preferred

This means:
1. When recording, you **must** use `-f S16_LE -r 48000 -c 2`
2. When playing audio, the file **must** be stereo. Mono files (like Piper's default output) must be converted to stereo before playback.
3. Conversion is handled with ffmpeg: `ffmpeg -i mono.wav -ac 2 -ar 48000 stereo.wav`

The device is detected as **card 2** on this system:
- ALSA capture device: `hw:2,0`
- ALSA playback device: `hw:2,0`

To verify device detection:
arecord -l aplay -l


To inspect hardware parameters:
arecord -D hw:2,0 --dump-hw-params


---

## Step 1: Set Up the Pi Environment

### 1.1 Update the System

sudo apt update && sudo apt upgrade -y


Updates the package list and upgrades all installed packages to their latest versions. This ensures compatibility and security before installing new software.

### 1.2 Install System Dependencies

sudo apt install -y python3 python3-pip python3-venv portaudio19-dev ffmpeg


| Package | Purpose |
|---|---|
| python3 | Python interpreter — the client script is written in Python |
| python3-pip | Python package installer |
| python3-venv | Allows creation of isolated Python virtual environments |
| portaudio19-dev | Audio I/O library — required by the sounddevice Python package to access the USB mic and speaker |
| ffmpeg | Audio/video conversion tool — used to convert Piper's mono output to stereo for the USB speaker |

### 1.3 Create the Project Directory

mkdir /voice-client cd /voice-client


Creates a dedicated folder at /home/admin/voice-client/ for all project files.

### 1.4 Create and Activate a Virtual Environment

python3 -m venv.venv source.venv/bin/activate


A virtual environment is an isolated Python installation. Packages installed inside it do not affect the rest of the system. When active, your terminal prompt will show (.venv) at the beginning.

**Important:** You must run `source.venv/bin/activate` every time you open a new terminal session before running the client script.

### 1.5 Install Python Packages

pip install vosk sounddevice requests numpy


| Package | Purpose |
|---|---|
| vosk | Offline speech-to-text engine |
| sounddevice | Python interface to capture audio from the USB mic |
| requests | HTTP client — sends transcribed text to the Windows server |
| numpy | Numerical library — required by sounddevice for audio data handling |

---

## Step 2: Download the Vosk Model

cd ~/voice-client wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip unzip vosk-model-small-en-us-0.15.zip


This downloads the **vosk-model-small-en-us-0.15** model (~40MB), a lightweight English speech recognition model optimized for low-resource devices like the Raspberry Pi.

After extraction, the model directory is located at:
~/voice-client/vosk-model-small-en-us-0.15/


Vosk runs entirely offline — no internet connection is needed for speech recognition after the model is downloaded.

---

## Step 3: Install Piper TTS

### 3.1 Download and Extract Piper

cd ~/voice-client wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz tar -xzf piper_linux_aarch64.tar.gz


This downloads the Piper TTS binary compiled for ARM64 Linux (the Pi 5's architecture). After extraction, the binary is located at:
~/voice-client/piper/piper


### 3.2 Download a Voice Model

cd piper wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json


Downloads the **en_US-lessac-medium** voice — a natural-sounding American English voice. Two files are required:
- `.onnx` — the neural network model
- `.onnx.json` — model configuration (sample rate, phoneme mapping, etc.)

### 3.3 Test Piper

Piper outputs mono audio at 22050 Hz by default, which is incompatible with the P10S USB speaker (stereo only). The workaround is to save to a file, convert with ffmpeg, then play.

**Generate speech:**
echo "Hello from your Raspberry Pi" | ~/voice-client/piper/piper
--model ~/voice-client/piper/en_US-lessac-medium.onnx
--output_file ~/voice-client/test_piper.wav


**Convert mono to stereo at 48000 Hz:**
ffmpeg -i /voice-client/test_piper.wav -ac 2 -ar 48000 /voice-client/test_piper_stereo.wav


**Play through USB speaker:**
aplay -D hw:2,0 ~/voice-client/test_piper_stereo.wav


You should hear "Hello from your Raspberry Pi" through the speaker.

---

## Folder Structure After Steps 1–3

~/voice-client/ ├──.venv/ Python virtual environment ├── vosk-model-small-en-us-0.15/ Vosk STT model │ ├── conf/ │ ├── graph/ │ ├── am/ │ └──... ├── piper/ Piper TTS │ ├── piper Piper binary (executable) │ ├── en_US-lessac-medium.onnx Voice model │ ├── en_US-lessac-medium.onnx.json Voice model config │ └──... ├── test.wav Mic test recording ├── test_piper.wav Piper mono output └── test_piper_stereo.wav Converted stereo output


---

## Verification Checklist

- [x] System updated and dependencies installed
- [x] Python virtual environment created and activated
- [x] Python packages installed (vosk, sounddevice, requests, numpy)
- [x] Vosk model downloaded and extracted
- [x] Piper binary downloaded and extracted
- [x] Piper voice model downloaded
- [x] USB mic records audio (arecord -D hw:2,0 -f S16_LE -r 48000 -c 2 -d 5 test.wav)
- [x] USB speaker plays audio (aplay -D hw:2,0 test.wav)
- [x] Piper TTS generates speech and plays through speaker (with ffmpeg stereo conversion)

---

## Next Steps

- Build the main Python client script (Vosk → HTTP → Piper pipeline)
- Configure the Windows server IP address and port
- Test end-to-end voice interaction
