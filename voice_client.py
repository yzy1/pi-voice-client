#!/usr/bin/env python3
"""
Raspberry Pi Voice Client
Connects to a remote FastAPI server for RAG + Ollama chat.
Uses Vosk for local STT and Piper for local TTS.
Supports physical buttons for pre-recorded questions.
"""

import os
import json
import wave
import struct
import subprocess
import tempfile
import queue
import sys
import threading

import numpy as np
import sounddevice as sd
import requests
from vosk import Model, KaldiRecognizer
from gpiozero import Button as GPIOButton

# =============================================================================
# CONFIGURATION
# =============================================================================

SERVER_URL = "http://192.168.68.119:8080"
VOSK_MODEL_PATH = os.path.expanduser("~/voice-client/vosk-model-small-en-us-0.15")
PIPER_BINARY = os.path.expanduser("~/voice-client/piper/piper")
PIPER_VOICE = os.path.expanduser("~/voice-client/piper/en_US-lessac-medium.onnx")

# Audio settings (must match your P10S USB device)
MIC_SAMPLE_RATE = 48000
MIC_CHANNELS = 2
MIC_DEVICE = "hw:2,0"
SPEAKER_DEVICE = "hw:2,0"

# Vosk needs 16000 Hz mono — we'll downsample from the mic's 48000 Hz stereo
VOSK_SAMPLE_RATE = 16000

# =============================================================================
# BUTTON CONFIGURATION
# =============================================================================
# Each button maps a GPIO pin (BCM number) to a pre-recorded question.
# To add more buttons, just add more entries to this dictionary.
#
# Wiring for each button:
#   One wire → GPIO pin
#   Other wire → any GND pin
#
# Current buttons:
#   Button 1: GPIO 17 (Physical Pin 11) + GND (Physical Pin 6)
#   Button 2: GPIO ?? (add when ready)
#   Button 3: GPIO ?? (add when ready)

BUTTON_QUESTIONS = {
    17: "Tell me something about the trunk space of this vehicle",
    27: "What is the fuel economy of this vehicle?",
    22: "What are the safety features of this vehicle?",
}

BUTTON_BOUNCE_TIME = 0.3  # seconds, to prevent double-triggers

# =============================================================================
# AUDIO QUEUE FOR RECORDING
# =============================================================================

audio_queue = queue.Queue()
button_queue = queue.Queue()


def audio_callback(indata, frames, time_info, status):
    """Called by sounddevice for each audio chunk from the mic."""
    if status:
        print(f"[Mic] {status}", file=sys.stderr)
    audio_queue.put(indata.copy())


# =============================================================================
# CONVERT STEREO 48kHz TO MONO 16kHz FOR VOSK
# =============================================================================

def stereo48k_to_mono16k(data):
    """
    Takes a numpy array of shape (N, 2) at 48000 Hz
    and returns a bytes object of mono 16-bit PCM at 16000 Hz.
    """
    # Take left channel only
    mono = data[:, 0]

    # Downsample from 48000 to 16000 (factor of 3)
    mono_downsampled = mono[::3]

    # Convert float32 to int16
    mono_int16 = (mono_downsampled * 32767).astype(np.int16)

    return mono_int16.tobytes()


# =============================================================================
# TEXT TO SPEECH (PIPER + FFMPEG + APLAY)
# =============================================================================

def speak(text):
    """Convert text to speech using Piper, convert to stereo, and play."""
    if not text:
        return

    print(f"[TTS] Speaking: {text[:80]}...")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as mono_file:
        mono_path = mono_file.name

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as stereo_file:
        stereo_path = stereo_file.name

    try:
        # Step 1: Generate mono WAV with Piper
        piper_proc = subprocess.run(
            [PIPER_BINARY, "--model", PIPER_VOICE, "--output_file", mono_path],
            input=text,
            capture_output=True,
            text=True,
            timeout=30
        )
        if piper_proc.returncode != 0:
            print(f"[TTS] Piper error: {piper_proc.stderr}")
            return

        # Step 2: Convert mono to stereo 48kHz with ffmpeg
        ffmpeg_proc = subprocess.run(
            ["ffmpeg", "-y", "-i", mono_path, "-ac", "2", "-ar", "48000", stereo_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        if ffmpeg_proc.returncode != 0:
            print(f"[TTS] ffmpeg error: {ffmpeg_proc.stderr}")
            return

        # Step 3: Play through USB speaker
        aplay_proc = subprocess.run(
            ["aplay", "-D", SPEAKER_DEVICE, stereo_path],
            capture_output=True,
            text=True,
            timeout=180
        )
        if aplay_proc.returncode != 0:
            print(f"[TTS] aplay error: {aplay_proc.stderr}")

    finally:
        # Clean up temp files
        for f in [mono_path, stereo_path]:
            try:
                os.unlink(f)
            except OSError:
                pass


# =============================================================================
# SEND TEXT TO SERVER
# =============================================================================

def ask_server(text):
    """Send a question to the FastAPI server and return the reply."""
    print(f"[Server] Asking: {text}")
    try:
        response = requests.post(
            f"{SERVER_URL}/agent/reply",
            json={"text": text, "system": "You are a car sales assistant helping customers understand the features and functions of their vehicle. Keep your answers concise and under 3 sentences. Your responses will be spoken aloud."},
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        reply = data.get("reply", "")
        print(f"[Server] Reply: {reply[:100]}...")
        return reply
    except requests.exceptions.ConnectionError:
        print("[Server] ERROR: Cannot connect to server. Is it running?")
        return "Sorry, I cannot reach the server."
    except requests.exceptions.Timeout:
        print("[Server] ERROR: Server took too long to respond.")
        return "Sorry, the server took too long to respond."
    except Exception as e:
        print(f"[Server] ERROR: {e}")
        return f"Sorry, there was an error: {e}"


# =============================================================================
# FIND THE USB AUDIO DEVICE INDEX FOR SOUNDDEVICE
# =============================================================================

def find_usb_mic_index():
    """Find the sounddevice index for the P10S USB mic."""
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if "P10S" in dev["name"] and dev["max_input_channels"] >= 2:
            print(f"[Mic] Found USB mic: {dev['name']} (index {i})")
            return i
    # Fallback: try to find any USB audio device
    for i, dev in enumerate(devices):
        if "USB" in dev["name"] and dev["max_input_channels"] >= 2:
            print(f"[Mic] Found USB device: {dev['name']} (index {i})")
            return i
    print("[Mic] WARNING: Could not find USB mic, using default")
    return None


# =============================================================================
# BUTTON HANDLER
# =============================================================================

def make_button_handler(gpio_pin):
    """Create a callback function for a specific button."""
    def handler():
        question = BUTTON_QUESTIONS[gpio_pin]
        print(f"\n[Button GPIO {gpio_pin}] Pressed! Question: {question}")
        button_queue.put(question)
    return handler


def setup_buttons():
    """Initialize all configured buttons."""
    buttons = []
    for gpio_pin, question in BUTTON_QUESTIONS.items():
        btn = GPIOButton(gpio_pin, pull_up=True, bounce_time=BUTTON_BOUNCE_TIME)
        btn.when_pressed = make_button_handler(gpio_pin)
        buttons.append(btn)
        print(f"[Button] GPIO {gpio_pin}: \"{question}\"")
    return buttons


# =============================================================================
# MAIN LOOP
# =============================================================================

def main():
    print("=" * 60)
    print("  Raspberry Pi Voice Client")
    print("  Server: " + SERVER_URL)
    print("=" * 60)

    # Load Vosk model
    print("[Vosk] Loading model...")
    if not os.path.exists(VOSK_MODEL_PATH):
        print(f"[Vosk] ERROR: Model not found at {VOSK_MODEL_PATH}")
        sys.exit(1)
    model = Model(VOSK_MODEL_PATH)
    recognizer = KaldiRecognizer(model, VOSK_SAMPLE_RATE)
    print("[Vosk] Model loaded.")

    # Find mic device
    mic_index = find_usb_mic_index()

    # Setup buttons
    print()
    buttons = setup_buttons()

    print()
    print("Commands:")
    print("  Speak into the mic — it will transcribe and ask the server")
    print("  Press a button — sends the pre-recorded question to the server")
    print("  Ctrl+C to exit")
    print()

    # Start mic stream
    stream = sd.InputStream(
        samplerate=MIC_SAMPLE_RATE,
        channels=MIC_CHANNELS,
        dtype="float32",
        device=mic_index,
        blocksize=4800,  # 100ms chunks at 48kHz
        callback=audio_callback
    )

    stream.start()
    print("[Mic] Listening... (speak or press a button)")

    try:
        while True:
            # Check for button presses first
            if not button_queue.empty():
                question = button_queue.get()
                print(f"\n[Button Question]: {question}")
                # Pause mic while processing
                stream.stop()
                # Ask server
                reply = ask_server(question)
                if reply:
                    print(f"[Answer]: {reply}")
                    speak(reply)
                # Resume mic
                stream.start()
                print("\n[Mic] Listening... (speak or press a button)")
                continue

            # Process audio chunks from the mic
            try:
                while not audio_queue.empty():
                    chunk = audio_queue.get()
                    # Convert stereo 48kHz to mono 16kHz for Vosk
                    mono_data = stereo48k_to_mono16k(chunk)

                    if recognizer.AcceptWaveform(mono_data):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").strip()
                        if text:
                            print(f"\n[You said]: {text}")
                            # Pause mic while processing
                            stream.stop()
                            # Ask server
                            reply = ask_server(text)
                            if reply:
                                print(f"[Answer]: {reply}")
                                speak(reply)
                            # Resume mic
                            stream.start()
                            print("\n[Mic] Listening... (speak or press a button)")
                    else:
                        partial = json.loads(recognizer.PartialResult())
                        partial_text = partial.get("partial", "").strip()
                        if partial_text:
                            print(f"\r[Hearing]: {partial_text}    ", end="", flush=True)

            except KeyboardInterrupt:
                raise

            # Small sleep to prevent CPU spinning
            sd.sleep(100)

    except KeyboardInterrupt:
        print("\n\n[Exit] Shutting down...")
    finally:
        stream.stop()
        stream.close()
        print("[Exit] Goodbye!")


# =============================================================================
# TEXT INPUT MODE (for typed questions)
# =============================================================================

def text_mode():
    """Simple text-only mode — type questions, hear answers."""
    print("=" * 60)
    print("  Raspberry Pi Text Client")
    print("  Server: " + SERVER_URL)
    print("=" * 60)
    print()
    print("Type a question and press Enter. Type 'quit' to exit.")
    print()

    while True:
        try:
            user_input = input("[You]: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                break

            reply = ask_server(user_input)
            if reply:
                print(f"[Answer]: {reply}")
                speak(reply)
            print()

        except KeyboardInterrupt:
            break
        except EOFError:
            break

    print("\n[Exit] Goodbye!")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--text":
        text_mode()
    else:
        main()
