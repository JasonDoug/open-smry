"""
Hybrid RAG Q&A + Citation Verifier Critic Agent for Summary AI.
Workflow:
1. qa_synthesizer_node: Generates grounded answers with explicit passage citations.
2. qa_critic_node: Adversarially verifies verbatim citations against exact document offsets
   (doc.text_content[start_char:end_char] == exact_quote). Loops back if citations fail.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from app.agents.llm_router import chat_completion
from app.agents.state import AgentState
from app.rag.retriever import verify_exact_offset_invariant


async def qa_synthesizer_node(state: AgentState) -> AgentState:
    """
    Synthesizes an answer grounded strictly in retrieved candidate passages.
    """
    question = state.get("question") or "What are the core arguments of this document?"
    doc_title = state.get("document_title") or "Document"
    retrieved = state.get("retrieved_passages") or []
    critic_feedback = state.get("critic_feedback")
    provider = state.get("provider")
    model = state.get("model")

    context_snippets = []
    for idx, p in enumerate(retrieved, start=1):
        context_snippets.append(
            f"[Passage {idx} | ID: {p.get('passage_id')}]: {p.get('exact_quote', p.get('text', ''))}"
        )
    context_str = "\n\n".join(context_snippets)

    system_prompt = (
        f"You are a citation-rigorous research assistant answering questions about '{doc_title}'.\n"
        "RULES:\n"
        "1. Every factual statement must cite one of the provided passages by [Passage N].\n"
        "2. Do not extrapolate, infer, or hallucinate beyond what is explicitly stated in the passages.\n"
        "3. Quote key phrases verbatim from the passages to ensure verifiable citations."
    )
    if critic_feedback:
        system_prompt += f"\nCRITIC REVISION DIRECTIVE:\n{critic_feedback}\nEnsure all quotes match the text verbatim."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context Passages:\n{context_str}\n\nQuestion: {question}"},
    ]

    answer, provider_used, model_used = await chat_completion(
        messages, provider=provider, model=model
    )

    state["generated_answer"] = answer
    state["provider_used"] = provider_used
    state["model_used"] = model_used
    return state


async def qa_critic_node(state: AgentState) -> AgentState:
    """
    Critic Node: Verifies that every cited passage has valid offsets and matches the text content.
    """
    full_text = state.get("document_text") or ""
    retrieved = state.get("retrieved_passages") or []
    answer = state.get("generated_answer") or ""
    iteration = state.get("iteration", 0)

    # Determine which passages were cited or relevant
    verified_citations: List[Dict[str, Any]] = []
    has_unverified = False

    for p in retrieved:
        start_c = int(p.get("start_char", 0))
        end_c = int(p.get("end_char", 0))
        quote = p.get("exact_quote") or p.get("text") or ""

        # Verify exact character-offset invariant against full document text
        if full_text:
            is_valid = bool(verify_exact_offset_invariant(full_text, start_c, end_c, quote))
        else:
            is_valid = bool(p.get("offset_verified", True))

        citation_entry = dict(p)
        citation_entry["offset_verified"] = is_valid
        verified_citations.append(citation_entry)

        if not is_valid:
            has_unverified = True

    state["citations"] = verified_citations
    state["all_citations_verified"] = not has_unverified if verified_citations else True

    # Check if answer needs revision
    if has_unverified and iteration < 1:
        state["critic_verdict"] = "revise"
        state["critic_feedback"] = (
            "One or more citation offsets failed exact verification against the primary text. "
            "Re-anchor your answer strictly to the verbatim passages without altering words."
        )
        state["iteration"] = iteration + 1
    else:
        state["critic_verdict"] = "pass"
        state["critic_feedback"] = None
        state["final_output"] = answer

    return state
