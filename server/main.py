# server/main.py
from __future__ import annotations

import json
import time
import struct
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from stt_vosk import create_recognizer
from agent_factory import create_agent

# Initialize the agent (reads AGENT_KIND from environment, defaults to "openai")
AGENT = create_agent()

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static hosting
BASE_DIR = Path(__file__).resolve().parent.parent
CLIENT_DIR = BASE_DIR / "client"
if not CLIENT_DIR.exists():
    raise RuntimeError(f"client directory not found: {CLIENT_DIR}")

app.mount("/client", StaticFiles(directory=str(CLIENT_DIR), html=False), name="client")


@app.get("/", response_class=FileResponse)
async def index():
    return FileResponse(CLIENT_DIR / "index.html")


# Health check
@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "ok"


# WebSocket Echo (for testing)
@app.websocket("/ws/echo")
async def ws_echo(ws: WebSocket):
    await ws.accept()
    print("[WS] echo connected")
    try:
        while True:
            msg = await ws.receive_text()
            print("[WS] recv:", msg)
            await ws.send_text(f"echo: {msg}")
    except WebSocketDisconnect:
        print("[WS] echo disconnected")


# ASR WebSocket (Vosk, local recognition on the Pi)
@app.websocket("/ws/asr")
async def ws_asr(ws: WebSocket):
    await ws.accept()
    print("[WS] asr connected")

    recognizer = None
    last_partial: Optional[str] = None

    # Throughput stats
    bytes_in_window = 0
    t0 = time.time()

    try:
        while True:
            msg = await ws.receive()

            if msg.get("type") == "websocket.disconnect":
                print(f"[WS] asr disconnected code={msg.get('code')}")
                break

            if msg.get("text") is not None:
                # Control message: start / stop
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    print("[ASR] invalid text:", msg["text"])
                    continue

                t = data.get("type")
                if t == "start":
                    sr = int(data.get("sampleRate") or 16000)
                    recognizer = create_recognizer(sr)
                    last_partial = None
                    await ws.send_text(json.dumps({"type": "ack", "sampleRate": sr}))
                    print(f"[ASR] start, sampleRate={sr}")

                elif t == "stop":
                    if recognizer is not None:
                        final_json = recognizer.FinalResult()
                        try:
                            final_data = json.loads(final_json or "{}")
                            text = (final_data.get("text") or "").strip()
                        except Exception:
                            text = ""
                        if text:
                            await ws.send_text(json.dumps({"type": "final", "text": text}))
                            print("[ASR] final:", text)
                    recognizer = None
                    last_partial = None
                continue

            # Audio frame
            if msg.get("bytes") is not None and recognizer is not None:
                chunk = msg["bytes"]
                bytes_in_window += len(chunk)

                ok = recognizer.AcceptWaveform(chunk)
                if ok:
                    res = recognizer.Result()
                    try:
                        obj = json.loads(res or "{}")
                        text = (obj.get("text") or "").strip()
                    except Exception:
                        text = ""
                    if text:
                        await ws.send_text(json.dumps({"type": "final", "text": text}))
                        print("[ASR] final:", text)
                    last_partial = None
                else:
                    part = recognizer.PartialResult()
                    try:
                        obj = json.loads(part or "{}")
                        ptxt = (obj.get("partial") or "").strip()
                    except Exception:
                        ptxt = ""
                    if ptxt and ptxt != last_partial:
                        last_partial = ptxt
                        await ws.send_text(json.dumps({"type": "partial", "text": ptxt}))
    except WebSocketDisconnect:
        print("[WS] asr disconnected (exception)")
    finally:
        print("[WS] asr closed")


# Agent text reply (pure text, no TTS)
@app.post("/agent/reply")
async def agent_reply(payload: dict = Body(...)):
    text = (payload.get("text") or "").strip()
    system = (payload.get("system") or "").strip() or None
    if not text:
        return {"reply": ""}

    try:
        reply = await AGENT.reply_async(text, system_prompt=system)
    except Exception as e:
        reply = f"[agent error] {e!r}"

    return {"reply": reply}
