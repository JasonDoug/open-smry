"""
Contextual Excerpt Analyst Agent for Summary AI.
Scoped strictly to a highlighted passage/excerpt within the reader interface.
Provides targeted explanations, definitions, critiques, and ad-hoc Q&A.
"""
from __future__ import annotations

from typing import Optional

from app.agents.llm_router import chat_completion
from app.agents.state import AgentState
from app.rag.retriever import verify_exact_offset_invariant


async def run_context_analyst_agent(state: AgentState) -> AgentState:
    """
    Analyzes a highlighted text selection within the document context.
    """
    selected_text = state.get("selected_text") or ""
    action_or_question = state.get("action_or_question") or "explain"
    start_char = state.get("start_char")
    end_char = state.get("end_char")
    full_text = state.get("document_text") or ""
    doc_title = state.get("document_title") or "Document"
    provider = state.get("provider")
    model = state.get("model")
    api_keys = state.get("api_keys")

    # Verify offset invariant if start/end chars are provided
    offset_verified = True
    if start_char is not None and end_char is not None and full_text:
        offset_verified = bool(
            verify_exact_offset_invariant(full_text, start_char, end_char, selected_text)
        )

    action_lower = action_or_question.lower().strip()
    if action_lower == "explain":
        action_directive = (
            "Explain the highlighted excerpt in clear, accessible language. "
            "Highlight its primary significance within the context of the document."
        )
    elif action_lower == "critique":
        action_directive = (
            "Critically analyze the highlighted excerpt. Identify underlying assumptions, "
            "potential weaknesses, or valid counterarguments."
        )
    elif action_lower == "define":
        action_directive = (
            "Define the central terminology and conceptual definitions introduced in this excerpt."
        )
    else:
        action_directive = f"Answer the user's specific question regarding the excerpt: '{action_or_question}'"

    system_prompt = (
        f"You are an analytical reading companion examining a highlighted passage from '{doc_title}'.\n"
        f"Directive: {action_directive}\n"
        "Ground your response directly in the provided excerpt."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Action: {action_or_question}\n\nHighlighted Excerpt:\n\"{selected_text}\"",
        },
    ]

    analysis, provider_used, model_used = await chat_completion(
        messages, provider=provider, model=model, api_keys=api_keys
    )

    state["context_analysis"] = analysis
    state["offset_verified"] = offset_verified
    state["provider_used"] = provider_used
    state["model_used"] = model_used
    state["final_output"] = analysis
    return state
