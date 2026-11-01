"""
Customizable AI Summarization Agent for Summary AI.
Supports:
1. Five Modes: TL;DR, Bullets, Key Takeaways, Executive Briefing, Custom Prompt.
2. Single-Pass for standard articles & Map-Reduce for long-form books/transcripts.
3. Reading-time-saved estimation and structured key point extraction.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from app.agents.llm_router import chat_completion
from app.agents.state import AgentState

SUMMARY_PROMPTS = {
    "tldr": (
        "You are an expert research analyst. Synthesize the provided document into a crisp, high-impact "
        "2-3 sentence executive TL;DR summary capturing the primary thesis, core argument, and ultimate conclusion."
    ),
    "bullets": (
        "You are an expert research analyst. Synthesize the provided document into 4-7 scannable, high-value bullet points. "
        "Each bullet must lead with a bold keyword, followed by concrete factual details and conclusions from the text."
    ),
    "takeaways": (
        "You are an expert research analyst. Extract the primary actionable insights, strategic takeaways, "
        "and intellectual implications from the provided document. Format as a numbered list."
    ),
    "executive": (
        "You are a senior intelligence analyst. Produce a structured Executive Research Briefing based strictly on the text. "
        "Use Markdown headers:\n"
        "## Executive Overview\n"
        "## Core Arguments & Primary Evidence\n"
        "## Critical Counterarguments & Nuances\n"
        "## Strategic Implications"
    ),
}


def _extract_key_points(summary_text: str) -> List[str]:
    """Extracts bullet or numbered items from generated summary text."""
    points: List[str] = []
    lines = summary_text.splitlines()
    for line in lines:
        cleaned = line.strip()
        if re.match(r"^[-*•]\s+", cleaned):
            points.append(re.sub(r"^[-*•]\s+", "", cleaned))
        elif re.match(r"^\d+\.\s+", cleaned):
            points.append(re.sub(r"^\d+\.\s+", "", cleaned))
    if not points and lines:
        # Fallback to non-empty paragraphs
        points = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")][:5]
    return points[:7]


async def run_summarizer_agent(state: AgentState) -> AgentState:
    """
    LangGraph Node executing single-pass or map-reduce document summarization.
    """
    mode = state.get("summary_mode") or "bullets"
    custom_prompt = state.get("custom_prompt")
    provider = state.get("provider")
    model = state.get("model")
    doc_title = state.get("document_title") or "Document"
    passages = state.get("passages") or []
    full_text = state.get("document_text") or "\n\n".join(p.get("text", "") for p in passages)

    system_instruction = (
        custom_prompt
        if mode == "custom" and custom_prompt
        else SUMMARY_PROMPTS.get(mode, SUMMARY_PROMPTS["bullets"])
    )

    provider_used = "openrouter"
    model_used = "openrouter/free"

    # Map-Reduce for long documents (>15 passages / long text)
    if len(passages) > 15:
        chunk_size = 10
        chunks = [passages[i : i + chunk_size] for i in range(0, len(passages), chunk_size)]
        intermediate_summaries: List[str] = []

        for idx, chunk in enumerate(chunks, start=1):
            chunk_text = "\n\n".join(p.get("text", "") for p in chunk)
            map_messages = [
                {
                    "role": "system",
                    "content": f"You are an assistant summarizing Section {idx} of a long document titled '{doc_title}'. Extract all key facts and claims.",
                },
                {"role": "user", "content": chunk_text},
            ]
            sub_summary, p_used, m_used = await chat_completion(
                map_messages, provider=provider, model=model
            )
            provider_used, model_used = p_used, m_used
            intermediate_summaries.append(f"### Section {idx} Summary:\n{sub_summary}")

        combined_sub_summaries = "\n\n".join(intermediate_summaries)
        reduce_messages = [
            {"role": "system", "content": f"{system_instruction}\nDocument Title: {doc_title}\nMode: {mode}"},
            {
                "role": "user",
                "content": f"Synthesize these section summaries into the final unified summary:\n\n{combined_sub_summaries}",
            },
        ]
        final_text, p_used, m_used = await chat_completion(
            reduce_messages, provider=provider, model=model
        )
        provider_used, model_used = p_used, m_used
    else:
        # Single-Pass Summarization
        messages = [
            {"role": "system", "content": f"{system_instruction}\nDocument Title: {doc_title}\nMode: {mode}"},
            {"role": "user", "content": f"Document Text:\n\n{full_text}"},
        ]
        final_text, provider_used, model_used = await chat_completion(
            messages, provider=provider, model=model
        )

    # Calculate reading time saved (assuming average reading speed of 220 wpm)
    orig_words = len(full_text.split())
    summary_words = len(final_text.split())
    words_saved = max(0, orig_words - summary_words)
    time_saved = max(1, words_saved // 220) if orig_words > 100 else 1

    key_points = _extract_key_points(final_text)

    state["summary_text"] = final_text
    state["key_points"] = key_points
    state["reading_time_saved_minutes"] = time_saved
    state["provider_used"] = provider_used
    state["model_used"] = model_used
    state["final_output"] = final_text
    return state
