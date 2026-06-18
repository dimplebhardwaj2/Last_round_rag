"""Runtime configuration, loaded from environment / .env."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(override=True)


@dataclass(frozen=True)
class InterviewConfig:
    """Per-interview settings chosen by the candidate."""

    role: str = "Software Engineer"
    level: str = "Mid-Level"  # Junior | Mid-Level | Senior
    style: str = "Technical"  # Friendly | Technical | Challenging
    interview_type: str = "behavioral"  # behavioral | coding | system_design
    max_questions: int = int(os.getenv("LR_MAX_QUESTIONS", "6"))
    resume_text: str = ""  # optional: candidate resume for personalized questions
    jd_text: str = ""      # optional: target job description
    use_rag: bool = True   # ground questions in the bank + resume/JD via retrieval


@dataclass(frozen=True)
class Settings:
    """App-wide settings."""

    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_api_keys: tuple[str, ...] = tuple(
        key.strip()
        for key in (
            os.getenv("GROQ_API_KEY_1", ""),
            os.getenv("GROQ_API_KEY_2", ""),
            os.getenv("GROQ_API_KEY_3", ""),
            os.getenv("GROQ_API_KEY", ""),
        )
        if key.strip()
    )
    model: str = os.getenv("LR_MODEL", "llama-3.3-70b-versatile").strip()
    temperature: float = 0.7


settings = Settings()
