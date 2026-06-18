"""The LAST ROUND interview graph (LangGraph StateGraph).

Flow:
    START -> interviewer -> human -> (route) -> interviewer | grade -> END

The `human` node uses LangGraph's `interrupt()` for human-in-the-loop: the graph
pauses after each interviewer turn, the caller supplies the candidate's answer,
and `Command(resume=...)` continues the run. A checkpointer makes it resumable.
"""

import json

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from engine.config import InterviewConfig
from engine.evaluation import AnswerAssessment, apply_constraints, assess_answer, build_constraints
from engine.llm import get_llm
from engine.prompts import first_question_instruction, grader_system, interviewer_system, turn_guidance
from engine.state import InterviewReport, InterviewState

NOTES_DELIM = "#NOTES#"
END_SIGNAL = "__END__"  # caller sends this to finish the interview early
_LLM_UNAVAILABLE: str | None = None

REPORT_SHAPE = """Respond with ONLY a JSON object (no markdown, no extra text) of this exact shape:
{
  "verdict": "one-line hire recommendation",
  "overall_score": <int 1-5>,
  "summary": "2-3 sentence overview",
  "criteria": [{"name": "...", "score": <int 1-5>, "comment": "cite the transcript"}],
  "strengths": ["..."],
  "improvements": ["..."],
  "model_answer": "brief example of a strong answer"
}"""


def _split_notes(text: str) -> tuple[str, str | None]:
    """Separate the candidate-visible message from the private #NOTES# part."""
    if NOTES_DELIM in text:
        visible, note = text.split(NOTES_DELIM, 1)
        return (visible.strip() or "Let's continue."), note.strip()
    return text.strip(), None


def _last_ai(messages: list[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            return m.content
    return ""


def _answer_assessments(messages: list[BaseMessage]) -> list[AnswerAssessment]:
    return [assess_answer(str(m.content)) for m in messages if isinstance(m, HumanMessage)]


def _recent_quality_pattern(assessments: list[AnswerAssessment]) -> str:
    if not assessments:
        return "no candidate answers yet"
    recent = assessments[-3:]
    labels = ", ".join(item.label for item in recent)
    weak = sum(1 for item in recent if item.label in {"non_evidence", "vague"})
    return f"last {len(recent)} answer labels: {labels}; weak/thin count: {weak}"


def _next_turn_behavior(assessments: list[AnswerAssessment]) -> str:
    if not assessments:
        return "Start with a role-appropriate scenario. Use private context when it makes the question more relevant."

    last = assessments[-1]
    recent_weak = sum(1 for item in assessments[-2:] if item.label in {"non_evidence", "vague"})
    recent_non_evidence = sum(1 for item in assessments[-2:] if item.label == "non_evidence")

    if last.label == "non_evidence" and recent_non_evidence >= 2:
        return (
            "Do not praise or rescue the answer. Move to a new concrete question, or if there is already too little "
            "evidence near the end, close the round. Hidden notes must mark repeated non-evidence."
        )
    if last.label == "non_evidence":
        return (
            "Give one firm recovery prompt asking for a concrete example or reasoning. Make clear that the current "
            "answer is not enough to evaluate, but do not give away the answer."
        )
    if last.label == "vague" and recent_weak >= 2:
        return (
            "Ask one precise follow-up for specifics, then move on if the candidate stays vague. Probe for evidence, "
            "not reassurance."
        )
    if last.label == "vague":
        return (
            "Ask a targeted follow-up that forces specificity: exact data, trade-off, failure mode, metric, or the "
            "candidate's personal action."
        )
    return (
        "Ask a deeper follow-up anchored in the candidate's concrete answer. Probe trade-offs, failure modes, scale, "
        "observability, or role-level judgment."
    )


# --- nodes ----------------------------------------------------------------

def retrieve_context_node(state: InterviewState) -> dict:
    """Pull relevant question-bank + resume/JD snippets to personalize the interview.

    Best-effort: if retrieval fails for any reason the interview proceeds without it.
    """
    cfg = state["config"]
    if not cfg.use_rag:
        return {"context": []}
    try:
        from engine.rag import build_retriever, retrieve  # lazy: heavy import only when running

        retriever = build_retriever(cfg.resume_text, cfg.jd_text)
        query = (
            f"{cfg.level} {cfg.role} {cfg.interview_type} interview questions "
            f"and relevant candidate background"
        )
        return {"context": retrieve(retriever, query)}
    except Exception:
        return {"context": []}


def interviewer_node(state: InterviewState) -> dict:
    """Generate the next interviewer utterance (question or follow-up)."""
    global _LLM_UNAVAILABLE
    cfg = state["config"]
    context = state.get("context") or []
    assessments = _answer_assessments(state["messages"])

    sys_text = interviewer_system(cfg)
    if context:
        sys_text += (
            "\n\nUse this private context to tailor your questions "
            "(the candidate cannot see it):\n" + "\n".join(f"- {c}" for c in context)
        )
    if cfg.resume_text or cfg.jd_text:
        sys_text += "\n\nPrivate personalization targets:"
        if cfg.resume_text:
            sys_text += "\n- Candidate resume/context is available. Probe claims with concrete follow-ups."
        if cfg.jd_text:
            sys_text += "\n- Target job description is available. Prefer questions that test its actual requirements."
    first_turn = state["question_count"] == 0 and not any(
        isinstance(m, AIMessage) for m in state["messages"]
    )
    if first_turn:
        sys_text += "\n\n" + first_question_instruction(cfg)
    else:
        last = assessments[-1] if assessments else AnswerAssessment("", "unknown", "no answer assessed")
        sys_text += "\n\n" + turn_guidance(
            label=last.label,
            reason=last.reason,
            pattern=_recent_quality_pattern(assessments),
            behavior=_next_turn_behavior(assessments),
        )

    if _LLM_UNAVAILABLE:
        visible, note = _fallback_interviewer_turn(cfg, state, assessments, context, first_turn)
    else:
        gen_input: list[BaseMessage] = [SystemMessage(sys_text)] + state["messages"]
        try:
            response = get_llm(max_tokens=350).invoke(gen_input)  # questions are short
            visible, note = _split_notes(response.content)
        except Exception as exc:
            _LLM_UNAVAILABLE = str(exc)
            visible, note = _fallback_interviewer_turn(cfg, state, assessments, context, first_turn)

    update: dict = {"messages": [AIMessage(visible)]}
    if note:
        update["notes"] = state["notes"] + [note]
    return update


def human_node(state: InterviewState) -> dict:
    """Pause for the candidate's answer (human-in-the-loop)."""
    answer = interrupt({"interviewer": _last_ai(state["messages"])})
    finished = isinstance(answer, str) and answer.strip().upper() == END_SIGNAL
    if finished:
        return {"finished": True}
    return {
        "messages": [HumanMessage(answer)],
        "question_count": state["question_count"] + 1,
    }


def grade_node(state: InterviewState) -> dict:
    """Produce the final structured feedback report."""
    cfg = state["config"]
    transcript = _render_transcript(state["messages"], state["notes"])
    constraints = build_constraints(state["messages"])
    try:
        return {"report": _grade(cfg, transcript, constraints)}
    except Exception as exc:  # never crash the run on a flaky free-tier response
        return {"report": _fallback_report(cfg, constraints, transcript, str(exc))}


def _grade(cfg: InterviewConfig, transcript: str, constraints) -> dict:
    """Grade via JSON mode (robust on small free models) + tolerant parsing."""
    if _LLM_UNAVAILABLE:
        return _fallback_report(cfg, constraints, transcript, _LLM_UNAVAILABLE)

    llm = get_llm(temperature=0, max_tokens=800).bind(response_format={"type": "json_object"})
    msg = llm.invoke(
        [
            SystemMessage(
                grader_system(cfg)
                + "\n\n"
                + constraints.prompt_block()
                + "\n\n"
                + REPORT_SHAPE
            ),
            HumanMessage("Evaluate this interview and produce the report:\n\n" + transcript),
        ]
    )
    data = json.loads(msg.content)
    # Small models sometimes emit nested arrays as JSON strings — re-parse them.
    for key in ("criteria", "strengths", "improvements"):
        if isinstance(data.get(key), str):
            try:
                data[key] = json.loads(data[key])
            except json.JSONDecodeError:
                pass
    report = InterviewReport(**data).model_dump()
    return apply_constraints(report, constraints)


def _fallback_interviewer_turn(
    cfg: InterviewConfig,
    state: InterviewState,
    assessments: list[AnswerAssessment],
    context: list[str],
    first_turn: bool,
) -> tuple[str, str]:
    """Deterministic interviewer used when the LLM provider is unavailable."""
    role = cfg.role or "the target role"
    level = cfg.level or "Mid-Level"
    kind = (cfg.interview_type or "behavioral").lower()
    asked = state["question_count"]
    context_hint = _context_hint(context, cfg)

    if first_turn:
        if "system" in kind:
            question = (
                f"Hi, let's start with a {level} {role} design scenario. "
                f"Design a reliable backend service for {context_hint}, and explain the main data flow."
            )
        elif "coding" in kind:
            question = (
                f"Hi, let's start with a {level} {role} coding scenario. "
                "Given a stream of user actions, how would you detect duplicate actions efficiently?"
            )
        else:
            question = (
                f"Hi, let's start with a {level} {role} interview question. "
                "Tell me about a difficult technical problem you handled and what you personally did."
            )
        return question, "Fallback mode. First question selected from role, level, interview type, and available context."

    last = assessments[-1] if assessments else AnswerAssessment("", "unknown", "no answer assessed")
    if last.label == "non_evidence":
        repeated = sum(1 for item in assessments[-2:] if item.label == "non_evidence") >= 2
        if repeated:
            return (
                "Let's move to a new question. How would you investigate an API that suddenly became much slower in production?",
                "Repeated non-evidence answer. Moved to a concrete production-debugging question instead of rescuing the same answer.",
            )
        return (
            "I need a concrete answer to evaluate you. Try again with the situation, your reasoning, and the result.",
            "Candidate gave non-evidence. One firm recovery prompt given; do not reward this unless the next answer improves.",
        )

    if last.label == "vague":
        return (
            "What specific metrics, data, or trade-offs would you look at first, and what would each one tell you?",
            "Candidate answer was vague. Follow-up asks for concrete evidence, not general reassurance.",
        )

    followups = [
        "What is the biggest failure mode in that approach, and how would you detect it in production?",
        "How would your answer change if traffic increased by 10x?",
        "What trade-off are you making, and what alternative would you reject?",
        "What data would you store, and how would you keep it consistent?",
    ]
    question = followups[min(asked - 1, len(followups) - 1)]
    return question, "Candidate gave a meaningful answer. Follow-up probes depth, trade-offs, scale, or production judgment."


def _context_hint(context: list[str], cfg: InterviewConfig) -> str:
    text = " ".join(context + [cfg.resume_text or "", cfg.jd_text or ""]).lower()
    if "payment" in text:
        return "checking payment status after a transaction"
    if "redis" in text or "cache" in text:
        return "serving read-heavy cached API responses"
    if "queue" in text or "event" in text:
        return "processing asynchronous jobs with retries"
    if "url shortener" in text:
        return "a URL shortener"
    return "a high-traffic API endpoint"


def _fallback_report(cfg: InterviewConfig, constraints, transcript: str, reason: str) -> dict:
    """Strict local report used when the provider fails during grading."""
    max_score = constraints.max_overall_score
    score = max(1, min(max_score, 3 if constraints.meaningful_answers else 1))
    if constraints.meaningful_answers == 0:
        verdict = "Not enough evidence to evaluate; no hire."
        summary = (
            "The candidate did not provide meaningful answers, so there is not enough evidence "
            "to evaluate role readiness. The LLM provider was unavailable, so this strict report "
            "was generated locally."
        )
        strengths = ["No clear strengths demonstrated from the provided answers."]
    else:
        verdict = "Needs more evidence before a positive recommendation."
        summary = (
            "The candidate provided some relevant evidence, but the local fallback grader cannot "
            "credit unstated strengths. The assessment is intentionally conservative because the "
            "LLM provider was unavailable."
        )
        strengths = ["Provided at least one answer with enough substance to evaluate."]

    report = {
        "verdict": verdict,
        "overall_score": score,
        "summary": summary,
        "criteria": [
            {
                "name": "Relevance",
                "score": score,
                "comment": "Scored conservatively from the candidate transcript and local answer-quality labels.",
            },
            {
                "name": "Depth of reasoning",
                "score": max(1, min(score, 2 if constraints.vague_answers else score)),
                "comment": "Answers need concrete examples, trade-offs, failure modes, and reasoning to score higher.",
            },
            {
                "name": "Communication clarity",
                "score": score,
                "comment": "Skipped, vague, or very short answers reduce the clarity score.",
            },
        ],
        "strengths": strengths,
        "improvements": [
            "Give direct answers instead of skipping or saying there is no answer.",
            "Use concrete examples with context, action, decision, trade-off, and outcome.",
            "Mention specific metrics, systems, failure modes, and debugging steps when answering technical questions.",
        ],
        "model_answer": (
            "A stronger answer would state assumptions, explain the approach step by step, discuss trade-offs "
            "and failure modes, and give concrete evidence from the candidate's own experience."
        ),
    }
    return apply_constraints(report, constraints)


def _render_transcript(messages: list[BaseMessage], notes: list[str]) -> str:
    lines: list[str] = []
    for m in messages:
        if isinstance(m, AIMessage):
            lines.append(f"INTERVIEWER: {m.content}")
        elif isinstance(m, HumanMessage):
            lines.append(f"CANDIDATE: {m.content}")
    if notes:
        lines.append("\nINTERVIEWER HIDDEN NOTES:")
        lines += [f"- {n}" for n in notes]
    return "\n".join(lines)


def _route(state: InterviewState) -> str:
    if state["finished"] or state["question_count"] >= state["config"].max_questions:
        return "grade"
    return "interviewer"


# --- assembly -------------------------------------------------------------

def build_graph(checkpointer=None):
    """Compile the interview graph. Pass a checkpointer for resumable sessions."""
    g = StateGraph(InterviewState)
    g.add_node("retrieve_context", retrieve_context_node)
    g.add_node("interviewer", interviewer_node)
    g.add_node("human", human_node)
    g.add_node("grade", grade_node)
    g.add_edge(START, "retrieve_context")
    g.add_edge("retrieve_context", "interviewer")
    g.add_edge("interviewer", "human")
    g.add_conditional_edges("human", _route, {"interviewer": "interviewer", "grade": "grade"})
    g.add_edge("grade", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


def initial_state(cfg: InterviewConfig) -> InterviewState:
    return {
        "config": cfg,
        "messages": [],
        "notes": [],
        "context": [],
        "question_count": 0,
        "finished": False,
        "report": None,
    }
