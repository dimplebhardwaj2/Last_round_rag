"""Local grading guardrails for LAST ROUND.

This module does not call an LLM. It extracts simple evidence-quality signals
from the transcript so the final grader cannot inflate weak interviews.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from langchain_core.messages import BaseMessage, HumanMessage

from engine.state import InterviewReport

NO_CLEAR_STRENGTH = "No clear strengths demonstrated from the provided answers."

NON_EVIDENCE_PHRASES = {
    "no",
    "no answer",
    "no idea",
    "dont know",
    "don't know",
    "do not know",
    "idk",
    "not sure",
    "skip",
    "pass",
    "nothing",
    "none",
    "na",
    "n/a",
}

FILLER_WORDS = {
    "good",
    "bad",
    "ok",
    "okay",
    "fine",
    "maybe",
    "probably",
    "things",
    "stuff",
    "something",
    "anything",
    "everything",
    "basically",
    "like",
}

CONCRETE_SIGNALS = {
    "because",
    "when",
    "where",
    "first",
    "then",
    "after",
    "result",
    "impact",
    "trade",
    "scale",
    "latency",
    "consistency",
    "availability",
    "database",
    "cache",
    "queue",
    "api",
    "test",
    "debug",
    "measure",
    "metric",
    "user",
    "team",
    "deadline",
    "resolved",
    "implemented",
    "designed",
    "built",
}


@dataclass(frozen=True)
class AnswerAssessment:
    answer: str
    label: str
    reason: str


@dataclass(frozen=True)
class EvaluationConstraints:
    total_answers: int
    meaningful_answers: int
    non_evidence_answers: int
    vague_answers: int
    max_overall_score: int
    no_clear_strengths: bool
    assessments: list[AnswerAssessment]

    def prompt_block(self) -> str:
        """Render constraints for the LLM grader."""
        if self.total_answers == 0:
            evidence_ratio = "0/0"
        else:
            evidence_ratio = f"{self.meaningful_answers}/{self.total_answers}"

        lines = [
            "STRICT LOCAL EVALUATION CONSTRAINTS:",
            f"- Meaningful answers: {evidence_ratio}.",
            f"- Non-evidence answers: {self.non_evidence_answers}.",
            f"- Vague/thin answers: {self.vague_answers}.",
            f"- Maximum allowed overall_score: {self.max_overall_score}.",
            "- You must not award an overall_score above this maximum.",
        ]
        if self.no_clear_strengths:
            lines.append(
                f'- Strengths must be exactly ["{NO_CLEAR_STRENGTH}"] unless the '
                "transcript directly proves a real strength."
            )

        if self.assessments:
            lines.append("- Answer quality labels:")
            for idx, item in enumerate(self.assessments, start=1):
                excerpt = _compact(item.answer)
                lines.append(f"  {idx}. {item.label}: {item.reason}. Answer: {excerpt}")
        return "\n".join(lines)


def assess_answer(answer: str) -> AnswerAssessment:
    text = " ".join((answer or "").strip().split())
    normalized = _normalize(text)
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]*", normalized)

    if not text:
        return AnswerAssessment(text, "non_evidence", "empty response")
    if normalized in NON_EVIDENCE_PHRASES:
        return AnswerAssessment(text, "non_evidence", "explicitly skipped or gave no answer")
    if _looks_like_gibberish(text, words):
        return AnswerAssessment(text, "non_evidence", "gibberish or unrelated token noise")
    if len(words) <= 3:
        return AnswerAssessment(text, "non_evidence", "too short to evaluate")

    concrete_hits = sum(1 for word in words if word in CONCRETE_SIGNALS)
    filler_hits = sum(1 for word in words if word in FILLER_WORDS)
    unique_ratio = len(set(words)) / max(1, len(words))

    if len(words) < 12 and concrete_hits == 0:
        return AnswerAssessment(text, "vague", "short answer with no concrete evidence")
    if len(words) < 20 and concrete_hits == 0 and filler_hits >= 1:
        return AnswerAssessment(text, "vague", "generic answer without examples or reasoning")
    if len(words) >= 8 and unique_ratio < 0.45:
        return AnswerAssessment(text, "vague", "repetitive answer with little substance")

    return AnswerAssessment(text, "meaningful", "contains enough substance to evaluate")


def build_constraints(messages: list[BaseMessage]) -> EvaluationConstraints:
    answers = [m.content for m in messages if isinstance(m, HumanMessage)]
    assessments = [assess_answer(str(answer)) for answer in answers]
    counts = Counter(item.label for item in assessments)
    total = len(assessments)
    meaningful = counts["meaningful"]
    non_evidence = counts["non_evidence"]
    vague = counts["vague"]

    if total == 0 or meaningful == 0:
        max_score = 1
    elif non_evidence > total / 2:
        max_score = 2
    elif non_evidence + vague > total / 2:
        max_score = 3
    elif meaningful < 2 and total >= 2:
        max_score = 3
    else:
        max_score = 5

    return EvaluationConstraints(
        total_answers=total,
        meaningful_answers=meaningful,
        non_evidence_answers=non_evidence,
        vague_answers=vague,
        max_overall_score=max_score,
        no_clear_strengths=meaningful == 0,
        assessments=assessments,
    )


def apply_constraints(report: dict, constraints: EvaluationConstraints) -> dict:
    """Clamp inflated scores and remove invented strengths from a report."""
    if not isinstance(report, dict):
        return report

    adjusted = dict(report)
    max_score = constraints.max_overall_score
    adjusted["overall_score"] = _clamp_score(adjusted.get("overall_score"), max_score)

    criteria = adjusted.get("criteria")
    if isinstance(criteria, list):
        adjusted["criteria"] = [_clamp_criterion(item, max_score) for item in criteria]

    if constraints.no_clear_strengths:
        adjusted["strengths"] = [NO_CLEAR_STRENGTH]
    else:
        adjusted["strengths"] = _filter_vague_strengths(adjusted.get("strengths"))

    if max_score <= 2:
        adjusted["verdict"] = _low_score_verdict(adjusted.get("verdict"), max_score)
        adjusted["summary"] = _low_score_summary(adjusted.get("summary"), constraints)
        adjusted["improvements"] = _ensure_low_score_improvements(adjusted.get("improvements"))

    # Re-validate after guardrail edits so the UI receives the expected shape.
    return InterviewReport(**adjusted).model_dump()


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9/' ]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _looks_like_gibberish(text: str, words: list[str]) -> bool:
    if not words:
        return bool(re.search(r"[^a-zA-Z0-9\s]{3,}", text))
    if re.search(r"[a-zA-Z]*\d+[a-zA-Z]+\d*|[a-zA-Z]+\d+[a-zA-Z]*", text):
        return True
    long_words = [w for w in words if len(w) >= 5]
    vowel_poor = [w for w in long_words if not re.search(r"[aeiou]", w.lower())]
    if long_words and len(vowel_poor) / len(long_words) > 0.6:
        return True
    return False


def _clamp_score(value, max_score: int) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        score = 1
    return max(1, min(max_score, score))


def _clamp_criterion(item, max_score: int):
    if not isinstance(item, dict):
        return item
    updated = dict(item)
    updated["score"] = _clamp_score(updated.get("score"), max_score)
    return updated


def _filter_vague_strengths(strengths) -> list[str]:
    if not isinstance(strengths, list):
        return [NO_CLEAR_STRENGTH]
    kept = []
    vague_patterns = (
        "communication",
        "confidence",
        "shows potential",
        "good understanding",
        "strong understanding",
        "problem solving",
    )
    for item in strengths:
        text = str(item).strip()
        lower = text.lower()
        if text and not any(pattern in lower for pattern in vague_patterns):
            kept.append(text)
    return kept or [NO_CLEAR_STRENGTH]


def _low_score_verdict(verdict, max_score: int) -> str:
    if max_score == 1:
        return "Not enough evidence to evaluate; no hire."
    return "Insufficient evidence for a positive recommendation."


def _low_score_summary(summary, constraints: EvaluationConstraints) -> str:
    if constraints.meaningful_answers == 0:
        return (
            "The candidate did not provide meaningful answers, so there is not enough "
            "evidence to evaluate role readiness. The interview performance should be "
            "treated as very weak."
        )
    return (
        "The candidate provided too little concrete evidence across the interview. "
        "Most answers were skipped, vague, or too thin to support a positive assessment."
    )


def _ensure_low_score_improvements(improvements) -> list[str]:
    base = [
        "Provide a direct answer instead of skipping or saying there is no answer.",
        "Use concrete examples with context, actions, decisions, and outcomes.",
        "Explain reasoning, trade-offs, and role-specific details so the interviewer has evidence to evaluate.",
    ]
    if not isinstance(improvements, list):
        return base
    existing = [str(item).strip() for item in improvements if str(item).strip()]
    merged = existing + [item for item in base if item not in existing]
    return merged[:5]


def _compact(text: str, limit: int = 120) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return repr(text)
    return repr(text[: limit - 3] + "...")
