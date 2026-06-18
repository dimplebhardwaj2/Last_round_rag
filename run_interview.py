"""LAST ROUND — terminal interview runner.

Proves the engine works end-to-end with no UI:
    python run_interview.py

Type your answers when prompted. Type /done to finish early and get feedback.
"""

import json
import uuid
from pathlib import Path

from langgraph.types import Command

from engine.config import InterviewConfig, settings
from engine.graph import END_SIGNAL, build_graph, initial_state


def _print_report(report: dict) -> None:
    print("\n" + "=" * 70)
    print("  FEEDBACK REPORT")
    print("=" * 70)
    if "error" in report:
        print("Grading error:", report["error"])
        return
    print(f"Verdict : {report['verdict']}  (overall {report['overall_score']}/5)")
    print(f"\n{report['summary']}\n")
    print("Per-criterion:")
    for c in report["criteria"]:
        print(f"  - {c['name']}: {c['score']}/5 - {c['comment']}")
    print("\nStrengths:")
    for s in report["strengths"]:
        print(f"  + {s}")
    print("\nImprovements:")
    for i in report["improvements"]:
        print(f"  > {i}")
    print(f"\nModel answer:\n  {report['model_answer']}")
    print("=" * 70)


def main() -> None:
    if not settings.groq_api_key:
        print("GROQ_API_KEY missing. Copy .env.example to .env and add a free key.")
        return

    print("=== LAST ROUND - mock interview ===")
    role = input("Role [Software Engineer]: ").strip() or "Software Engineer"
    level = input("Level (Junior/Mid-Level/Senior) [Mid-Level]: ").strip() or "Mid-Level"
    itype = input("Type (behavioral/coding/system_design) [behavioral]: ").strip() or "behavioral"

    resume_text = ""
    resume_path = input("Path to resume .txt for tailored questions (optional): ").strip().strip('"')
    if resume_path:
        try:
            resume_text = Path(resume_path).read_text(encoding="utf-8")
            print(f"Loaded resume ({len(resume_text)} chars).")
        except OSError as exc:
            print(f"Could not read resume ({exc}); continuing without it.")

    cfg = InterviewConfig(role=role, level=level, interview_type=itype, resume_text=resume_text)
    graph = build_graph()
    thread = {"configurable": {"thread_id": str(uuid.uuid4())}}

    print(f"\nModel: {settings.model} | up to {cfg.max_questions} questions. Type /done to stop.\n")

    # First run goes until the graph interrupts for the candidate's first answer.
    graph.invoke(initial_state(cfg), thread)

    while True:
        state = graph.get_state(thread)
        if not state.next:
            break  # graph reached the end -> grading done

        pending = next((t.interrupts[0].value for t in state.tasks if t.interrupts), None)
        if pending is None:
            break

        print(f"INTERVIEWER: {pending['interviewer']}\n")
        answer = input("YOU: ").strip()
        print()
        if answer.lower() in {"/done", "/quit", "/stop"}:
            resume_value = END_SIGNAL
        else:
            resume_value = answer or "(no response)"  # empty resume is rejected by LangGraph
        graph.invoke(Command(resume=resume_value), thread)

    report = graph.get_state(thread).values.get("report")
    if report:
        _print_report(report)
        with open("last_interview_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print("\nSaved -> last_interview_report.json")
    else:
        print("Interview ended without a report.")


if __name__ == "__main__":
    main()
