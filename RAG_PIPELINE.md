# LAST ROUND RAG Pipeline

This document explains how uploaded resume and job-description files become private interview context.

## Flow

```text
Setup UI
  upload resume PDF/TXT/MD
  upload JD PDF/TXT/MD
        |
        v
Browser document extraction
  PDF -> PDF.js text extraction
  TXT/MD -> File.text()
        |
        v
sessionStorage interview config
  resume_text
  jd_text
        |
        v
FastAPI WebSocket /ws/interview
  InterviewConfig(resume_text, jd_text)
        |
        v
LangGraph retrieve_context node
  build_retriever(resume_text, jd_text)
        |
        v
LlamaIndex BM25 retriever
  question_bank.json as TextNode objects
  resume/JD as chunked Document nodes
        |
        v
Top-4 private context snippets
        |
        v
Interviewer system prompt
  "Use this private context to tailor your questions"
```

## Current Retrieval Design

- Retrieval type: sparse BM25 keyword retrieval
- Library: LlamaIndex
- Question bank: `data/question_bank.json`
- Resume/JD chunking: `SentenceSplitter(chunk_size=256, chunk_overlap=20)`
- Top-k retrieved snippets: `4`

## What The Candidate Sees

The candidate does not see retrieved context directly. The retrieved snippets are added only to the interviewer prompt, so the LLM can ask more personalized questions.

## What The Interviewer Uses It For

The interviewer can use uploaded documents to probe:

- resume project claims
- required job skills
- role-specific systems
- relevant tools and technologies
- production/debugging experience
- seniority-level expectations

## What This Is Not Yet

- Not FAISS/vector retrieval
- Not embedding-based retrieval
- Not hybrid dense + sparse retrieval
- Not backend PDF parsing

