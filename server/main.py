# server/main.py
from __future__ import annotations

import json
import time
import struct
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from tts_piper import piper_tts
from stt_vosk import create_recognizer

import traceback

from agent_factory import create_agent
AGENT = create_agent()   # 读取 AGENT_KIND，默认 openai；

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态托管
BASE_DIR = Path(__file__).resolve().parent.parent
CLIENT_DIR = BASE_DIR / "client"
if not CLIENT_DIR.exists():
    raise RuntimeError(f"client directory not found: {CLIENT_DIR}")

app.mount("/client", StaticFiles(directory=str(CLIENT_DIR), html=False), name="client")


@app.get("/", response_class=FileResponse)
async def index():
    return FileResponse(CLIENT_DIR / "index.html")


# 探活
@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "ok"


# WebSocket Echo
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


# ASR WebSocket（Vosk，本地识别）
@app.websocket("/ws/asr")
async def ws_asr(ws: WebSocket):
    await ws.accept()
    print("[WS] asr connected")

    recognizer = None
    last_partial: Optional[str] = None

    # 吞吐统计
    bytes_in_window = 0
    t0 = time.time()

    try:
        while True:
            msg = await ws.receive()

            if msg.get("type") == "websocket.disconnect":
                print(f"[WS] asr disconnected code={msg.get('code')}")
                break

            if msg.get("text") is not None:
                # 控制消息：start / stop
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

            # 音频帧
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


# TTS（Piper，本地合成整段 WAV）
@app.post("/tts")
async def tts_endpoint(payload: dict = Body(...)):
    text = (payload.get("text") or "").strip()
    voice = (payload.get("voice") or "").strip() or None
    if not text:
        return Response(content=b"", media_type="audio/wav")

    try:
        wav_bytes = piper_tts.synth(text=text, model_path=voice)
        return Response(content=wav_bytes, media_type="audio/wav")
    except Exception as e:
        err = f"[TTS] error: {e}".encode("utf-8")
        return Response(content=err, media_type="text/plain", status_code=500)


# Agent 文本回复（纯文本）
@app.post("/agent/reply")
async def agent_reply(payload: dict = Body(...)):
    text = (payload.get("text") or "").strip()
    system = (payload.get("system") or "").strip() or None
    if not text:
        return {"reply": ""}

    try:
        # 使用AGENT(默认是 OpenAIAdapter，内部仍然调用 chat_once）
        reply = await AGENT.reply_async(text, system_prompt=system)
    except Exception as e:
        reply = f"[agent error] {e!r}"

    return {"reply": reply}


# /agent/tts，整段WAV
@app.post("/agent/tts")
async def agent_tts(payload: dict = Body(...)):
    user_text = (payload.get("text") or "").strip()
    system = (payload.get("system") or "").strip() or None
    voice = (payload.get("voice") or "").strip() or None

    if not user_text:
        return Response(content=b"", media_type="audio/wav")

    try:
        # 通过AGENT获取回答文本
        reply = await AGENT.reply_async(user_text, system_prompt=system)
        reply = (reply or "").strip()
    except Exception as e:
        err = f"[agent error] {e}".encode("utf-8")
        return Response(content=err, media_type="text/plain", status_code=500)

    if not reply:
        return Response(content=b"", media_type="audio/wav")

    try:
        wav_bytes = piper_tts.synth(text=reply, model_path=voice)
        return Response(content=wav_bytes, media_type="audio/wav")
    except Exception as e:
        err = f"[TTS] error: {e}".encode("utf-8")
        return Response(content=err, media_type="text/plain", status_code=500)


# TTS 流式（s16le）
@app.post("/tts/stream")
async def tts_stream_endpoint(payload: dict = Body(...)):
    text = (payload.get("text") or "").strip()
    voice = (payload.get("voice") or "").strip() or None
    if not text:
        return Response(content=b"", media_type="audio/L16; rate=16000; channels=1")

    try:
        gen = await piper_tts.stream_s16le(text=text, model_path=voice, sample_rate=16000, chunk_ms=20)
        return StreamingResponse(gen, media_type="audio/L16; rate=16000; channels=1")
    except Exception as e:
        detail = f"{e.__class__.__name__}: {e}"
        tb = traceback.format_exc()
        if tb:
            detail += "\n" + tb
        raise HTTPException(status_code=500, detail=detail)


# Agent TTS流式
@app.post("/agent/tts/stream")
async def agent_tts_stream(payload: dict = Body(...)):
    """
    输入: { "text": "...", "system": "(可选)", "voice": "en_US-amy-medium.onnx(可选)" }
    输出: 裸PCM流 (audio/L16; rate=16000; channels=1)
    """
    user_text = (payload.get("text") or "").strip()
    system = (payload.get("system") or "").strip() or None
    voice = (payload.get("voice") or "").strip() or None
    if not user_text:
        raise HTTPException(status_code=400, detail="empty text")

    try:
        # 通过AGENT获取回答文本
        answer = await AGENT.reply_async(user_text, system_prompt=system)
        answer = (answer or "").strip()
        if not answer:
            raise RuntimeError("empty agent reply")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    try:
        gen = await piper_tts.stream_s16le(text=answer, model_path=voice, sample_rate=16000, chunk_ms=20)
        return StreamingResponse(gen, media_type="audio/L16; rate=16000; channels=1")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")
