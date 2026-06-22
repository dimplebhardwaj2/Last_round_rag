# LAST ROUND
REAL DEMO : https://huggingface.co/spaces/DimpleBhardwaj/Last-Round

**Agentic RAG Interview Intelligence Platform**

LAST ROUND is an AI-powered mock interview platform that conducts adaptive interviews, personalizes questions with retrieval-augmented generation, and produces strict evidence-based feedback reports.

It combines a **LangGraph interview workflow**, **LlamaIndex BM25 retrieval**, **Groq LLMs**, **FastAPI WebSockets**, and a browser-based interview UI with speech support.

> Practice like it is the final round. Get feedback like a real interviewer actually paid attention.

---

## Highlights

- **Agentic interview workflow** powered by LangGraph
- **RAG-grounded questioning** using LlamaIndex BM25 over a curated question bank
- **Resume/JD-aware personalization** through required document upload
- **Adaptive follow-ups** based on answer quality and previous turns
- **Strict LLM-as-a-Judge evaluation** with score caps and fake-strength filtering
- **Real-time browser interview experience** using FastAPI WebSockets
- **Voice-enabled UX** with browser speech recognition and TTS fallback
- **Multi-key Groq fallback** for rate limits, exhausted keys, or provider failures
- **Local fallback interviewer/report** when the LLM provider is unavailable

---

## Demo Flow

```text
Landing Page
   -> Interview Setup
   -> Live AI Interview
   -> Structured Feedback Report
```

The candidate selects a role, seniority level, interview type, interviewer style, max questions, and uploads both a resume and job description. The platform extracts the document text, runs a multi-turn interview, and generates a structured report.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| Agent Workflow | LangGraph |
| LLM Integration | LangChain, Groq |
| Retrieval | LlamaIndex BM25 |
| Validation | Pydantic |
| Realtime | WebSockets |
| Frontend | HTML, CSS, Vanilla JavaScript |
| Voice | Browser Speech Recognition, Browser Speech Synthesis, edge-tts |
| State | LangGraph MemorySaver, per-session thread IDs |

---

## Architecture

```text
Candidate Setup
  role / level / style / interview type / resume upload / JD upload
        |
        v
FastAPI WebSocket Server
        |
        v
LangGraph Interview Engine
        |
        +--> retrieve_context
        |       LlamaIndex BM25 over question bank + resume/JD text
        |
        +--> interviewer
        |       Groq LLM generates role-aware question or follow-up
        |
        +--> human
        |       LangGraph interrupt waits for candidate answer
        |
        +--> route
        |       continue interview or move to grading
        |
        +--> grade
                LLM-as-a-Judge + local strict scoring guardrails
```

---

## LangGraph Workflow

LAST ROUND uses a 4-node graph:

1. **retrieve_context**  
   Retrieves relevant snippets from the question bank, uploaded resume, and uploaded job description.

2. **interviewer**  
   Generates one focused question at a time and adapts follow-ups based on the candidate answer.

3. **human**  
   Pauses the graph using LangGraph `interrupt()` until the candidate answers.

4. **grade**  
   Produces a structured feedback report using an LLM-as-a-Judge pattern and local score validation.

Graph route:

```text
START -> retrieve_context -> interviewer -> human -> interviewer | grade -> END
```

---

## RAG Pipeline

The current RAG implementation uses **sparse keyword retrieval**, not vector embeddings.

```text
question_bank.json + extracted resume text + extracted JD text
        |
        v
LlamaIndex TextNode / Document objects
        |
        v
SentenceSplitter for long resume/JD content
chunk_size = 256, chunk_overlap = 20
        |
        v
BM25Retriever, top_k = 4
        |
        v
Private context injected into interviewer prompt
```

Document ingestion and retrieval facts:

- Question bank: `data/question_bank.json`
- Curated prompts: **22**
- Upload types: **PDF, TXT, MD**
- PDF extraction: **client-side PDF.js**
- Top-k retrieval: **4**
- Resume/JD chunking: **256 tokens**, **20-token overlap**
- Retrieval engine: **LlamaIndex BM25Retriever**

---

## Strict Evaluation System

The feedback engine is designed to avoid inflated or generic scoring.

It includes:

- 1-5 overall score
- Per-criterion scoring
- Verdict
- Summary
- Strengths
- Improvements
- Model answer
- Hidden interviewer notes
- Local answer-quality classification
- Score caps for weak or non-evidence answers
- Fake-strength filtering

Examples of non-evidence answers:

```text
no answer
I don't know
skip
pass
empty response
gibberish
very short unrelated answers
```

If the candidate gives no meaningful answers, the system prevents the report from producing a generous score.

---

## Frontend Experience

The browser UI includes:

- Landing page
- Interview setup page
- Live interview room
- Feedback report page
- Animated interviewer presence
- Transcript panel
- Progress tracker
- Speech input
- Text-to-speech output
- Camera preview toggle
- Live assessment focus panel

No frontend build step is required.

---

## API Surface

| Route | Type | Purpose |
|---|---|---|
| `/api/health` | HTTP GET | Health check |
| `/api/tts` | HTTP POST | Generate MP3 speech using edge-tts |
| `/ws/interview` | WebSocket | Live interview protocol |
| `/` | Static | Serves frontend |

WebSocket messages:

```json
{ "type": "start", "config": { "...": "..." } }
{ "type": "answer", "text": "candidate answer" }
{ "type": "end" }
```

Server responses:

```json
{ "type": "question", "text": "interviewer question" }
{ "type": "report", "report": { "...": "..." } }
{ "type": "error", "message": "..." }
```

---

## Project Structure

```text
last-round/
├── engine/
│   ├── config.py          # env settings + interview config
│   ├── evaluation.py      # strict local grading guardrails
│   ├── graph.py           # LangGraph interview workflow
│   ├── llm.py             # Groq/LangChain factory + multi-key fallback
│   ├── prompts.py         # interviewer and grader prompts
│   ├── rag.py             # LlamaIndex BM25 retrieval
│   └── state.py           # graph state + Pydantic report schema
├── data/
│   └── question_bank.json # curated role/type-tagged questions
├── web/
│   ├── index.html
│   ├── setup.html
│   ├── interview.html
│   ├── report.html
│   ├── css/
│   ├── js/
│   └── assets/
├── server.py              # FastAPI app + WebSocket API
├── run_interview.py       # terminal interview runner
├── test_evaluation.py     # offline strict evaluation tests
├── test_interview_flow.py # offline interview flow tests
├── test_llm_fallback.py   # offline key fallback tests
├── test_engine.py         # real Groq engine tests
├── test_server.py         # real WebSocket server test
└── requirements.txt
```

---

## Setup

### 1. Create a virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example file:

```bash
cp .env.example .env
```

Add your Groq keys:

```env
GROQ_API_KEY_1=your_primary_groq_key
GROQ_API_KEY_2=your_backup_groq_key
GROQ_API_KEY_3=your_second_backup_groq_key

LR_MODEL=llama-3.1-8b-instant
LR_MAX_QUESTIONS=6
```

Get a Groq key from:

```text
https://console.groq.com/keys
```

Do not commit real API keys.

---

## Run The Web App

```bash
uvicorn server:app --host 127.0.0.1 --port 7860
```

Open:

```text
http://127.0.0.1:7860
```

---

## Run In Terminal

```bash
python run_interview.py
```

Type `/done` to finish early and generate the report.

---

## Tests

Offline tests that do **not** call Groq:

```bash
python test_evaluation.py
python test_interview_flow.py
python test_llm_fallback.py
```

Tests that call the real LLM provider:

```bash
python test_engine.py
python test_server.py
```

Use the real-provider tests carefully because they consume API quota.

---

## Resume-Ready Summary

**LAST ROUND – Agentic RAG Interview Platform | FastAPI, LangGraph, Groq, LlamaIndex BM25, Pydantic, WebSockets**

- Built a 4-node LangGraph interview engine handling retrieval, interviewer generation, candidate interruption, and grading across 7 roles, 3 seniority levels, and 3 interview modes.
- Developed a BM25-based RAG layer with PDF/TXT/MD resume and JD ingestion, 256-token chunks, 20-token overlap, and top-4 retrieval over 22 curated interview prompts plus uploaded candidate/job context.
- Implemented strict LLM evaluation with 1-5 score validation, structured criteria scoring, answer-quality classification, score caps, and fake-strength filtering.
- Shipped a browser-based interview experience with 3 API surfaces, real-time WebSocket communication, TTS, speech input, and a 4-page frontend.

---

## Current Limitations

- Current retrieval is BM25-based, not FAISS/vector embedding-based.
- PDF extraction runs in the browser via PDF.js; there is no backend PDF parser yet.
- Persistent database storage is not implemented; sessions use in-memory LangGraph checkpointing.

---

## Roadmap

- Dense vector retrieval with embeddings
- Hybrid retrieval and reranking
- Persistent interview history
- User accounts
- Docker deployment
- Hosted deployment on Hugging Face Spaces or a cloud VM

---

## Security Note

Never commit `.env` or real API keys. The repository ignores `.env` by default.

If an API key is leaked, rotate it immediately from the provider console.
