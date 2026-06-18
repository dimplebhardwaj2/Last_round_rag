"""LAST ROUND — FastAPI server.

Wraps the LangGraph interview engine behind HTTP + WebSocket and serves the
single-page frontend. Designed for a single Hugging Face Docker Space:
one process serves both the API and the UI on one port.

Run locally:
    uvicorn server:app --host 0.0.0.0 --port 7860
"""

import asyncio
import mimetypes
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from pydantic import BaseModel

from engine.config import InterviewConfig
from engine.graph import END_SIGNAL, build_graph, initial_state

# On Windows, mimetypes reads the registry and may serve .js as text/plain, which
# browsers refuse to execute as ES modules. Force correct types for all platforms.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

app = FastAPI(title="LAST ROUND")
WEB_DIR = Path(__file__).resolve().parent / "web"
TTS_VOICE = os.getenv("LR_TTS_VOICE", "en-US-AriaNeural")  # free edge-tts neural voice

# One compiled graph (in-memory checkpointer); each WebSocket gets its own thread_id.
graph = build_graph()


def _client_error_message(exc: Exception) -> str:
    """Turn provider/backend exceptions into safe, actionable UI messages."""
    raw = str(exc)
    lower = raw.lower()
    if "organization has been restricted" in lower or "organization_restricted" in lower:
        return (
            "The LLM provider rejected this API key because its organization is restricted. "
            "Create or use a different Groq API key, update GROQ_API_KEY in .env, and restart the server."
        )
    if "api key" in lower or "authentication" in lower or "unauthorized" in lower:
        return "The LLM API key is missing or invalid. Update GROQ_API_KEY in .env and restart the server."
    if "rate limit" in lower or "too many requests" in lower:
        return "The LLM provider rate limit was reached. Wait a minute, then try again."
    return f"Interview engine failed: {raw}"


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)  # no icon yet; avoids 404 noise


class TTSRequest(BaseModel):
    text: str


@app.post("/api/tts")
async def tts(req: TTSRequest) -> Response:
    """Free neural TTS via edge-tts -> MP3 bytes (drives the Live2D lip-sync)."""
    text = (req.text or "").strip()[:800]
    if not text:
        return Response(status_code=400)
    try:
        import edge_tts

        audio = bytearray()
        communicate = edge_tts.Communicate(text, TTS_VOICE)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
        if not audio:
            return Response(status_code=503)
        return Response(content=bytes(audio), media_type="audio/mpeg")
    except Exception:
        # Client falls back to browser SpeechSynthesis when this is unavailable.
        return Response(status_code=503)


def _pending_question(thread: dict) -> str | None:
    """Return the interviewer's pending question, or None if the graph finished."""
    state = graph.get_state(thread)
    if not state.next:
        return None
    for task in state.tasks:
        if task.interrupts:
            return task.interrupts[0].value.get("interviewer")
    return None


@app.websocket("/ws/interview")
async def interview(ws: WebSocket) -> None:
    await ws.accept()
    thread = {"configurable": {"thread_id": str(uuid.uuid4())}}
    try:
        start = await ws.receive_json()
        if start.get("type") != "start":
            await ws.send_json({"type": "error", "message": "expected a 'start' message"})
            return

        c = start.get("config", {})
        cfg = InterviewConfig(
            role=(c.get("role") or "Software Engineer").strip(),
            level=(c.get("level") or "Mid-Level").strip(),
            style=(c.get("style") or "Technical").strip(),
            interview_type=(c.get("interview_type") or "behavioral").strip(),
            resume_text=(c.get("resume_text") or "").strip(),
            jd_text=(c.get("jd_text") or "").strip(),
            max_questions=int(c.get("max_questions") or 6),
        )

        # Run until the graph interrupts for the first answer.
        await asyncio.to_thread(graph.invoke, initial_state(cfg), thread)
        await ws.send_json({"type": "question", "text": _pending_question(thread)})

        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")
            if mtype == "end":
                resume = END_SIGNAL
            elif mtype == "answer":
                resume = (msg.get("text") or "").strip() or "(no response)"
            else:
                continue

            await asyncio.to_thread(graph.invoke, Command(resume=resume), thread)
            question = _pending_question(thread)
            if question is not None:
                await ws.send_json({"type": "question", "text": question})
            else:
                report = graph.get_state(thread).values.get("report")
                await ws.send_json({"type": "report", "report": report})
                break
    except WebSocketDisconnect:
        return
    except Exception as exc:  # surface engine errors to the client instead of dropping
        try:
            await ws.send_json({"type": "error", "message": _client_error_message(exc)})
        except Exception:
            pass


# Serve the multi-page frontend. Mounted last so /api/* and /ws/* take precedence.
# html=True -> "/" serves index.html; /setup.html, /css/*, /js/* are served directly.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
