# server/main.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

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

# Static hosting - optional, only if client folder exists
# Railway root is set to "server/", so we need to go up one level to find "client/"
BASE_DIR = Path(__file__).resolve().parent  # This is /app/server
CLIENT_DIR = BASE_DIR.parent / "client"     # This is /app/client

if not CLIENT_DIR.exists():
    # Fallback for local development
    CLIENT_DIR = Path(__file__).resolve().parent.parent / "client"

if CLIENT_DIR and CLIENT_DIR.exists():
    print(f"Client directory found at: {CLIENT_DIR}")
    app.mount("/client", StaticFiles(directory=str(CLIENT_DIR), html=False), name="client")

    @app.get("/", response_class=FileResponse)
    async def index():
        return FileResponse(CLIENT_DIR / "index.html")
else:
    print(f"Warning: client directory not found at: {CLIENT_DIR}, web UI disabled")
    
    @app.get("/", response_class=PlainTextResponse)
    async def index():
        return "API server is running. Use /health to check status or /agent/reply for queries."


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
