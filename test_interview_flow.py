"""Offline tests for interviewer flow guidance.

These tests do not call Groq or any external API.
"""

from langchain_core.messages import HumanMessage

from engine.graph import _answer_assessments, _next_turn_behavior, _recent_quality_pattern


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" :: {detail}" if detail else ""))
    if not condition:
        raise AssertionError(name)


def behavior_for(*answers: str) -> str:
    assessments = _answer_assessments([HumanMessage(answer) for answer in answers])
    return _next_turn_behavior(assessments)


def test_first_turn_starts_scenario() -> None:
    behavior = _next_turn_behavior([])
    check("first turn starts with scenario", "Start" in behavior and "private context" in behavior)


def test_one_no_answer_gets_recovery_prompt() -> None:
    behavior = behavior_for("no answer")
    check("single no-answer gets firm recovery", "firm recovery prompt" in behavior, behavior)
    check("single no-answer does not move on immediately", "Move to a new" not in behavior, behavior)


def test_repeated_no_answer_moves_on() -> None:
    behavior = behavior_for("no answer", "I don't know")
    check("repeated no-answer moves on", "Move to a new concrete question" in behavior, behavior)
    check("repeated no-answer forbids praise", "Do not praise" in behavior, behavior)


def test_vague_answer_gets_specificity_probe() -> None:
    behavior = behavior_for("I would check logs")
    check("vague answer asks for specifics", "specific" in behavior.lower(), behavior)
    check("vague answer probes evidence", "trade-off" in behavior or "failure mode" in behavior, behavior)


def test_meaningful_answer_gets_deeper_followup() -> None:
    behavior = behavior_for(
        "I would use Redis with a short TTL, keep Postgres as the source of truth, "
        "and track latency metrics because stale payment status is risky."
    )
    check("meaningful answer gets deeper follow-up", "deeper follow-up" in behavior, behavior)
    check("meaningful answer probes trade-offs", "trade-offs" in behavior, behavior)


def test_recent_quality_pattern_summarizes_answers() -> None:
    assessments = _answer_assessments([
        HumanMessage("no answer"),
        HumanMessage("I would check logs"),
        HumanMessage("I would inspect database slow queries because latency increased."),
    ])
    pattern = _recent_quality_pattern(assessments)
    check("quality pattern includes labels", "non_evidence" in pattern and "vague" in pattern, pattern)


def main() -> None:
    test_first_turn_starts_scenario()
    test_one_no_answer_gets_recovery_prompt()
    test_repeated_no_answer_moves_on()
    test_vague_answer_gets_specificity_probe()
    test_meaningful_answer_gets_deeper_followup()
    test_recent_quality_pattern_summarizes_answers()
    print("\nALL OFFLINE INTERVIEW FLOW CHECKS PASSED")


if __name__ == "__main__":
    main()
