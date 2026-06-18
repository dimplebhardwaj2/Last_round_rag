"""Retrieval layer (LlamaIndex + BM25).

Grounds the interviewer in (a) a curated question bank and (b) extracted resume
and job-description text, so questions are personalized.

We use BM25 keyword retrieval (pure Python, no model download, no torch) so it
runs on any Python incl. 3.13 and on a free CPU HF Space. Swapping to vector
embeddings later is a one-line change (replace the retriever). Index is built
in-memory — HF Space disk is ephemeral.
"""

import json
from pathlib import Path

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TextNode
from llama_index.retrievers.bm25 import BM25Retriever

_QUESTION_BANK = Path(__file__).resolve().parent.parent / "data" / "question_bank.json"
_TOP_K = 4
_splitter = SentenceSplitter(chunk_size=256, chunk_overlap=20)


def load_question_bank() -> list[str]:
    items = json.loads(_QUESTION_BANK.read_text(encoding="utf-8"))
    return [f"[{i['role']} / {i['type']}] {i['question']}" for i in items]


def build_retriever(resume_text: str = "", jd_text: str = "") -> BM25Retriever:
    """Build a BM25 retriever over the question bank + uploaded resume/JD text."""
    nodes = [TextNode(text=q) for q in load_question_bank()]
    for label, body in (("CANDIDATE RESUME", resume_text), ("JOB DESCRIPTION", jd_text)):
        if body and body.strip():
            doc = Document(text=f"{label}:\n{body.strip()}")
            nodes.extend(_splitter.get_nodes_from_documents([doc]))
    return BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=_TOP_K)


def retrieve(retriever: BM25Retriever, query: str) -> list[str]:
    """Return the most relevant snippets for a query."""
    return [n.get_content().strip() for n in retriever.retrieve(query)]
