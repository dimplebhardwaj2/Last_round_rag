"""Proper end-to-end tests for the LAST ROUND engine (hits the real Groq API).

Run:  python test_engine.py
Covers: natural completion (auto-wrap), early /done exit, adversarial answers,
report-schema validity, and that the interviewer adapts to candidate answers.
"""

import sys
import time
import uuid

from langgraph.types import Command

from engine.config import InterviewConfig, settings
from engine.graph import END_SIGNAL, build_graph, initial_state
from engine.state import InterviewReport

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def run_scripted(cfg: InterviewConfig, answers: list[str]) -> tuple[list[str], dict | None]:
    """Drive a full interview with canned answers. Returns (questions, report)."""
    graph = build_graph()
    thread = {"configurable": {"thread_id": str(uuid.uuid4())}}
    graph.invoke(initial_state(cfg), thread)

    questions: list[str] = []
    i = 0
    while True:
        state = graph.get_state(thread)
        if not state.next:
            break
        pending = next((t.interrupts[0].value for t in state.tasks if t.interrupts), None)
        if pending is None:
            break
        questions.append(pending["interviewer"])
        ans = answers[i] if i < len(answers) else "/done"
        i += 1
        if str(ans).strip().lower() == "/done":
            resume = END_SIGNAL
        else:
            resume = str(ans).strip() or "(no response)"  # empty resume is rejected by LangGraph
        graph.invoke(Command(resume=resume), thread)

    report = graph.get_state(thread).values.get("report")
    return questions, report


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((PASS if condition else FAIL, name, detail))
    print(f"[{PASS if condition else FAIL}] {name}" + (f" :: {detail}" if detail else ""))


def valid_report(report: dict | None) -> bool:
    if not report or "error" in report:
        return False
    try:
        InterviewReport(**report)  # re-validate the schema
        return True
    except Exception:
        return False


def test_natural_completion() -> None:
    print("\n--- Scenario 1: natural completion (auto-wrap at max questions) ---")
    cfg = InterviewConfig(role="Backend Engineer", level="Senior",
                          interview_type="system_design", max_questions=2)
    answers = [
        "I'd start by clarifying scale: reads vs writes, expected QPS, and latency SLOs.",
        "For 100k writes/sec I'd shard by user id, use a write-ahead log, and add a CDC pipeline to keep read replicas eventually consistent.",
    ]
    questions, report = run_scripted(cfg, answers)
    check("S1 produced >= 2 interviewer turns", len(questions) >= 2, f"{len(questions)} turns")
    check("S1 produced a valid report", valid_report(report))
    if valid_report(report):
        check("S1 overall_score in 1..5", report["overall_score"] in range(1, 6),
              f"score={report['overall_score']}")
        check("S1 has >=1 criterion", len(report["criteria"]) >= 1,
              f"{len(report['criteria'])} criteria")


def test_early_done() -> None:
    print("\n--- Scenario 2: early /done exit ---")
    cfg = InterviewConfig(role="Software Engineer", level="Junior",
                          interview_type="behavioral", max_questions=6)
    questions, report = run_scripted(cfg, [
        "I once disagreed with my tech lead about a deadline; I raised data on scope risk and we re-planned.",
        "/done",
    ])
    check("S2 stopped early (did not reach 6 turns)", len(questions) < 6, f"{len(questions)} turns")
    check("S2 produced a valid report", valid_report(report))


def test_adversarial() -> None:
    print("\n--- Scenario 3: adversarial answers (empty + gibberish) ---")
    cfg = InterviewConfig(role="Data Scientist", level="Mid-Level",
                          interview_type="behavioral", max_questions=2)
    questions, report = run_scripted(cfg, ["", "asd9f8 qwsdf zzz lorem ipsum 42 %%%"])
    check("S3 did not crash on junk input", report is not None)
    check("S3 produced a valid report", valid_report(report))


def test_adaptivity() -> None:
    print("\n--- Scenario 4: interviewer adapts to the candidate's answer ---")
    # use_rag=False isolates pure conversational follow-up from question-bank context
    cfg = InterviewConfig(role="Software Engineer", level="Mid-Level",
                          interview_type="behavioral", max_questions=2, use_rag=False)
    questions, _ = run_scripted(cfg, [
        "I built a Kafka-based event pipeline that cut report latency from hours to seconds.",
        "I'd add schema registry and dead-letter queues to harden it.",
    ])
    follow_up = questions[1].lower() if len(questions) > 1 else ""
    adapted = any(k in follow_up for k in ("kafka", "pipeline", "event", "latency", "queue", "schema"))
    check("S4 follow-up references the candidate's topic", adapted,
          f"follow-up: {questions[1][:80]}..." if len(questions) > 1 else "no follow-up")


def test_rag_retrieval() -> None:
    print("\n--- Scenario 5: RAG retrieval surfaces resume content (no API) ---")
    from engine.rag import build_retriever, retrieve

    retriever = build_retriever(
        resume_text="Expert in Rust and embedded systems with RTOS scheduling experience.",
    )
    hits = " ".join(retrieve(retriever, "embedded firmware and real-time scheduling")).lower()
    check("S5 retrieval surfaces resume keywords",
          any(k in hits for k in ("rust", "embedded", "rtos")), f"hits: {hits[:80]}")


def test_resume_aware_interview() -> None:
    print("\n--- Scenario 6: resume-aware interview completes with a report ---")
    cfg = InterviewConfig(
        role="Backend Engineer", level="Senior", interview_type="system_design", max_questions=2,
        resume_text="Built a distributed rate limiter and URL shortener serving 200M req/day on Redis and Cassandra.",
    )
    _, report = run_scripted(cfg, [
        "I'd clarify QPS and consistency requirements, then sketch the data model.",
        "I'd use consistent hashing for sharding and a sliding-window limiter in Redis.",
    ])
    check("S6 resume-aware interview produced a valid report", valid_report(report))


def main() -> None:
    if not settings.groq_api_key:
        print("GROQ_API_KEY missing — add it to .env first.")
        sys.exit(1)
    print(f"Testing engine with model: {settings.model}")

    def pace():
        # Groq free tier = 6000 tokens/min. Space API-heavy scenarios so they
        # don't stack inside one window.
        print("  ...pacing 30s to respect the free-tier token/min limit...")
        time.sleep(30)

    test_natural_completion(); pace()
    test_early_done(); pace()
    test_adversarial(); pace()
    test_adaptivity()
    test_rag_retrieval()  # no API call
    pace()
    test_resume_aware_interview()

    failed = [r for r in results if r[0] == FAIL]
    print("\n" + "=" * 60)
    print(f"RESULTS: {len(results) - len(failed)}/{len(results)} checks passed")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
