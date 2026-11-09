"""
LangGraph Multi-Agent State Definition for Summary AI.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    # Core Routing & Task Info
    task_type: Literal["summarize", "ask_document", "ask_context", "chat"]
    provider: Optional[str]
    model: Optional[str]
    provider_used: str
    model_used: str
    iteration: int

    # Document Context
    document_id: Optional[str]
    document_title: Optional[str]
    document_text: Optional[str]
    passages: List[Dict[str, Any]]

    # Summarization Task State
    summary_mode: Optional[Literal["tldr", "bullets", "takeaways", "executive", "custom"]]
    custom_prompt: Optional[str]
    summary_text: Optional[str]
    key_points: List[str]
    reading_time_saved_minutes: int

    # Verifiable Q&A & Research Task State
    question: Optional[str]
    retrieved_passages: List[Dict[str, Any]]
    generated_answer: Optional[str]
    citations: List[Dict[str, Any]]
    all_citations_verified: bool
    critic_verdict: Literal["pass", "revise"]
    critic_feedback: Optional[str]

    # Contextual Excerpt Analysis State
    selected_text: Optional[str]
    start_char: Optional[int]
    end_char: Optional[int]
    action_or_question: Optional[str]
    context_analysis: Optional[str]
    offset_verified: bool

    # Conversational Chat State
    messages: List[Dict[str, str]]
    final_output: Optional[str]
