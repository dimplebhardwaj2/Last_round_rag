"""End-to-end test of the FastAPI server over the real WebSocket protocol.

Run:  python test_server.py
Uses Starlette's TestClient (in-process), so no separate server needs to run.
Drives a full interview: start -> questions -> answers -> /end -> report.
"""

import sys

from fastapi.testclient import TestClient

from engine.config import settings
from server import app

ANSWERS = [
    "I'd start by clarifying the requirements and constraints before proposing anything.",
    "I'd weigh consistency vs availability and pick based on the product's needs.",
]


def main() -> None:
    if not settings.groq_api_key:
        print("GROQ_API_KEY missing — add it to .env first.")
        sys.exit(1)

    client = TestClient(app)

    # 1) health
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok", "health failed"
    print("[PASS] /api/health")

    # 2) the page is served
    r = client.get("/")
    assert r.status_code == 200 and "Last Round" in r.text, "index not served"
    print("[PASS] / serves the frontend")

    # 3) full interview over WebSocket
    with client.websocket_connect("/ws/interview") as ws:
        ws.send_json({
            "type": "start",
            "config": {"role": "Backend Engineer", "level": "Senior",
                       "interview_type": "system_design", "max_questions": 3,
                       "resume_text": "Scaled a payments API on Postgres and Redis."},
        })
        first = ws.receive_json()
        assert first["type"] == "question" and first["text"], "no first question"
        print(f"[PASS] first question received :: {first['text'][:70]}...")

        # answer twice, then end early
        questions = 1
        for ans in ANSWERS:
            ws.send_json({"type": "answer", "text": ans})
            msg = ws.receive_json()
            assert msg["type"] in ("question", "report"), f"unexpected: {msg}"
            if msg["type"] == "report":
                break
            questions += 1

        ws.send_json({"type": "end"})
        final = ws.receive_json()
        assert final["type"] == "report", f"expected report, got {final['type']}"
        report = final["report"]
        assert report and "error" not in report, f"bad report: {report}"
        assert report["overall_score"] in range(1, 6), "score out of range"
        print(f"[PASS] interview produced a report :: {report['verdict']} ({report['overall_score']}/5)")
        print(f"       asked {questions} question(s), {len(report.get('criteria', []))} criteria")

    print("\n==============================")
    print("ALL SERVER CHECKS PASSED")
    print("==============================")


if __name__ == "__main__":
    main()
