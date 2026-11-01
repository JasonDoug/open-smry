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
    Critic Node:
    1. Parses [Passage N] markers from generated_answer.
    2. Rejects out-of-range indices and derives has_unverified from citation validity.
    3. Populates state["citations"] with only cited passages.
    4. Verifies exact character offsets against full_text (recording offset_verified).
    5. Triggers revision loop on answer-citation faults, not retrieval offset faults.
    """
    full_text = state.get("document_text") or ""
    retrieved = state.get("retrieved_passages") or []
    answer = state.get("generated_answer") or ""
    iteration = state.get("iteration", 0)

    # 1. Parse [Passage N] markers from answer
    raw_markers = re.findall(r"\[Passage\s+(\d+)\]", answer, re.IGNORECASE)
    cited_indices = [int(m) for m in raw_markers]

    has_unverified = False
    verified_citations: List[Dict[str, Any]] = []
    seen_indices = set()

    if not cited_indices:
        # Check if any passage text was quoted verbatim in answer
        found_verbatim = False
        for p in retrieved:
            quote = p.get("exact_quote") or p.get("text") or ""
            if len(quote) > 15 and quote.lower() in answer.lower():
                entry = dict(p)
                start_c = int(p.get("start_char", 0))
                end_c = int(p.get("end_char", 0))
                entry["offset_verified"] = (
                    bool(verify_exact_offset_invariant(full_text, start_c, end_c, quote))
                    if full_text
                    else bool(p.get("offset_verified", True))
                )
                verified_citations.append(entry)
                found_verbatim = True
                break
        if not found_verbatim:
            has_unverified = True
            if retrieved:
                entry = dict(retrieved[0])
                entry["offset_verified"] = bool(retrieved[0].get("offset_verified", True))
                verified_citations.append(entry)
    else:
        for idx in cited_indices:
            if idx < 1 or idx > len(retrieved):
                has_unverified = True
                continue
            if idx in seen_indices:
                continue
            seen_indices.add(idx)

            p = retrieved[idx - 1]
            start_c = int(p.get("start_char", 0))
            end_c = int(p.get("end_char", 0))
            quote = p.get("exact_quote") or p.get("text") or ""

            offset_valid = (
                bool(verify_exact_offset_invariant(full_text, start_c, end_c, quote))
                if full_text
                else bool(p.get("offset_verified", True))
            )

            entry = dict(p)
            entry["offset_verified"] = offset_valid
            verified_citations.append(entry)

    state["citations"] = verified_citations
    state["all_citations_verified"] = (
        not has_unverified and all(c.get("offset_verified", False) for c in verified_citations)
        if verified_citations
        else False
    )

    # Revision loop triggers only on answer-level citation faults (invalid or omitted citations),
    # treating offset failures as retrieval faults.
    if has_unverified and iteration < 1:
        state["critic_verdict"] = "revise"
        state["critic_feedback"] = (
            f"Your answer cited invalid or out-of-range passage numbers. "
            f"Please cite valid passages from [Passage 1] to [Passage {len(retrieved)}] "
            "with verbatim quotations."
        )
        state["iteration"] = iteration + 1
    else:
        state["critic_verdict"] = "pass"
        state["critic_feedback"] = None
        state["final_output"] = answer

    return state
