"""Offline tests for strict evaluation guardrails.

These tests do not call Groq or any external API.
"""

from langchain_core.messages import AIMessage, HumanMessage

from engine.evaluation import (
    NO_CLEAR_STRENGTH,
    apply_constraints,
    assess_answer,
    build_constraints,
)


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" :: {detail}" if detail else ""))
    if not condition:
        raise AssertionError(name)


def sample_report(score: int = 5) -> dict:
    return {
        "verdict": "Lean hire",
        "overall_score": score,
        "summary": "The candidate communicated well and showed strong problem solving.",
        "criteria": [
            {
                "name": "Relevance",
                "score": score,
                "comment": "The candidate answered the question.",
            },
            {
                "name": "Depth",
                "score": score,
                "comment": "The candidate showed depth.",
            },
        ],
        "strengths": [
            "Good communication skills.",
            "Strong problem solving ability.",
        ],
        "improvements": ["Add more detail."],
        "model_answer": "A stronger answer would include context, action, trade-offs, and outcome.",
    }


def test_no_answer_is_non_evidence() -> None:
    item = assess_answer("no answer")
    check("no answer classified as non-evidence", item.label == "non_evidence", item.reason)


def test_gibberish_is_non_evidence() -> None:
    item = assess_answer("asd9f8 qwsdf zzz lorem ipsum 42 %%%")
    check("gibberish classified as non-evidence", item.label == "non_evidence", item.reason)


def test_empty_interview_caps_score_at_one() -> None:
    constraints = build_constraints([
        AIMessage("Tell me about a difficult project."),
        HumanMessage("no answer"),
        AIMessage("Can you give any example?"),
        HumanMessage("pass"),
    ])
    report = apply_constraints(sample_report(5), constraints)
    check("all non-evidence caps overall score at 1", report["overall_score"] == 1)
    check("criteria scores capped at 1", all(c["score"] == 1 for c in report["criteria"]))
    check("fake strengths removed", report["strengths"] == [NO_CLEAR_STRENGTH])
    check("verdict becomes strict", "no hire" in report["verdict"].lower())


def test_mostly_weak_interview_caps_score() -> None:
    constraints = build_constraints([
        AIMessage("How would you design a rate limiter?"),
        HumanMessage("I don't know"),
        AIMessage("Try to reason through storage and limits."),
        HumanMessage("maybe cache stuff"),
        AIMessage("Any trade-offs?"),
        HumanMessage("I'd use Redis with a sliding window because it gives predictable per-user limits and fast reads."),
    ])
    report = apply_constraints(sample_report(5), constraints)
    check("mostly weak answers cap score at 3 or below", report["overall_score"] <= 3)
    check("criteria scores respect cap", all(c["score"] <= 3 for c in report["criteria"]))


def test_strong_answer_not_unfairly_capped() -> None:
    constraints = build_constraints([
        AIMessage("How would you design a URL shortener?"),
        HumanMessage(
            "First I would clarify read and write scale, latency goals, and retention. "
            "Then I would generate short ids, store mappings in a database, cache hot links, "
            "and discuss consistency trade-offs for redirects and analytics."
        ),
        AIMessage("How would you handle failures?"),
        HumanMessage(
            "I would add retries with backoff, health checks, database replication, and metrics "
            "for error rate and latency so the team can detect failures quickly."
        ),
    ])
    check("strong answers allow high scores", constraints.max_overall_score == 5)


def main() -> None:
    test_no_answer_is_non_evidence()
    test_gibberish_is_non_evidence()
    test_empty_interview_caps_score_at_one()
    test_mostly_weak_interview_caps_score()
    test_strong_answer_not_unfairly_capped()
    print("\nALL OFFLINE EVALUATION CHECKS PASSED")


if __name__ == "__main__":
    main()
