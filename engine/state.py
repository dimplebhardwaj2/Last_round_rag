"""Graph state and the structured grading schema."""

from typing import Annotated, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from engine.config import InterviewConfig


class InterviewState(TypedDict):
    """State carried through the interview graph.

    ``messages`` holds the full conversation (system + interviewer + candidate).
    ``add_messages`` appends rather than overwrites on each node return.
    """

    config: InterviewConfig
    messages: Annotated[list[BaseMessage], add_messages]
    notes: list[str]            # interviewer's private observations
    context: list[str]          # retrieved RAG snippets (resume/JD/question bank)
    question_count: int         # candidate answers given so far
    finished: bool              # candidate asked to stop
    report: Optional[dict]      # final feedback (set by grade node)


class CriterionScore(BaseModel):
    name: str = Field(description="Criterion, e.g. 'Problem solving'")
    score: int = Field(ge=1, le=5, description="1 (poor) to 5 (excellent)")
    comment: str = Field(description="Specific justification citing the transcript")


class InterviewReport(BaseModel):
    """Structured feedback produced at the end of the interview."""

    verdict: str = Field(description="One-line hire recommendation, e.g. 'Lean hire'")
    overall_score: int = Field(ge=1, le=5)
    summary: str = Field(description="2-3 sentence overview of the performance")
    criteria: list[CriterionScore] = Field(description="Per-criterion breakdown")
    strengths: list[str]
    improvements: list[str] = Field(description="Concrete, actionable next steps")
    model_answer: str = Field(description="A brief example of a strong answer/approach")
