"""
Sprint 4 FastAPI Router: LangGraph Multi-Agent Orchestration & Multi-LLM System
Endpoints:
- POST /api/v1/summarize (5 modes: tldr, bullets, takeaways, executive, custom)
- GET /api/v1/documents/{document_id}/summaries
- POST /api/v1/documents/{document_id}/ask (Verifiable Q&A with Critic verification)
- POST /api/v1/ask-context (Contextual excerpt analyst)
- POST /api/v1/chat (Conversational chat with SSE text/event-stream streaming)
- GET /api/v1/chat/{thread_id}
- DELETE /api/v1/chat/{thread_id}
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import compiled_agent_graph
from app.agents.llm_router import stream_chat_completion
from app.agents.state import AgentState
from app.db.models import ChatMessage, ChatThread, Document, ReaderSession, SummaryRecord
from app.db.session import get_db
from app.rag.retriever import hybrid_search_passages
from app.schemas.domain import (
    AskContextRequest,
    AskContextResponse,
    AskDocumentRequest,
    AskDocumentResponse,
    ChatMessageRequest,
    ChatMessageSchema,
    ChatThreadResponse,
    RetrievedPassageSchema,
    SummarizeRequest,
    SummaryResponse,
)

logger = logging.getLogger(__name__)

agents_router = APIRouter(
    prefix="/api/v1",
    tags=["Sprint 4: LangGraph Multi-Agent System & Multi-LLM Router"],
)


def _resolve_api_keys(
    db: Session,
    session_id: Optional[str],
    override: Optional[Dict[str, str]],
) -> Dict[str, str]:
    """
    Builds the effective api_keys mapping for a request: per-request overrides
    take precedence over the keys persisted on the reader session (settings page).
    Session columns use <provider>_api_key names; the LLM router expects bare
    provider names (anthropic, openai, gemini, openrouter).
    """
    keys: Dict[str, str] = {}
    if session_id:
        sess = db.get(ReaderSession, session_id)
        if sess:
            column_map = {
                "anthropic": sess.anthropic_api_key,
                "openai": sess.openai_api_key,
                "gemini": sess.gemini_api_key,
                "openrouter": sess.openrouter_api_key,
            }
            keys.update({k: v for k, v in column_map.items() if v})
    if override:
        keys.update({k: v for k, v in override.items() if v})
    return keys


@agents_router.post(
    "/summarize",
    response_model=SummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a Structured AI Summary (TL;DR, Bullets, Key Takeaways, Executive, or Custom Prompt)",
)
async def generate_document_summary(
    payload: SummarizeRequest,
    db: Session = Depends(get_db),
) -> SummaryResponse:
    doc = db.get(Document, payload.document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{payload.document_id}' not found",
        )

    passages_data = [
        {
            "id": p.id,
            "paragraph_index": p.paragraph_index,
            "chapter_title": p.chapter_title,
            "start_char": p.start_char,
            "end_char": p.end_char,
            "text": p.text,
        }
        for p in doc.passages
    ]

    initial_state: AgentState = {
        "task_type": "summarize",
        "document_id": doc.id,
        "document_title": doc.title,
        "document_text": doc.text_content,
        "passages": passages_data,
        "summary_mode": payload.mode,
        "custom_prompt": payload.custom_prompt,
        "provider": payload.provider,
        "model": payload.model,
        "api_keys": _resolve_api_keys(db, payload.session_id, payload.api_keys),
        "iteration": 0,
    }

    result = await compiled_agent_graph.ainvoke(initial_state)

    summary_content = result.get("summary_text") or result.get("final_output") or ""
    key_points = result.get("key_points") or []
    time_saved = int(result.get("reading_time_saved_minutes", 1))
    provider_used = result.get("provider_used", payload.provider or "openrouter")
    model_used = result.get("model_used", payload.model or "openrouter/free")

    # Persist summary record in DB
    summary_record = SummaryRecord(
        document_id=doc.id,
        mode=payload.mode,
        provider=provider_used,
        model_id=model_used,
        custom_prompt=payload.custom_prompt,
        content=summary_content,
        key_points_json=json.dumps(key_points),
        citations_json="[]",
    )
    db.add(summary_record)
    db.commit()
    db.refresh(summary_record)

    return SummaryResponse(
        id=summary_record.id,
        document_id=doc.id,
        mode=payload.mode,
        content=summary_content,
        key_points=key_points,
        word_count=len(summary_content.split()),
        reading_time_saved_minutes=time_saved,
        provider_used=provider_used,
        model_used=model_used,
        created_at=summary_record.created_at,
    )


@agents_router.get(
    "/documents/{document_id}/summaries",
    response_model=List[SummaryResponse],
    summary="List All Generated AI Summaries for a Document",
)
def list_document_summaries(
    document_id: str,
    db: Session = Depends(get_db),
) -> List[SummaryResponse]:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )

    stmt = select(SummaryRecord).filter(SummaryRecord.document_id == document_id).order_by(SummaryRecord.created_at.desc())
    records = list(db.scalars(stmt).all())

    summaries = []
    for r in records:
        try:
            kp = json.loads(r.key_points_json or "[]")
        except Exception:
            kp = []
        summaries.append(
            SummaryResponse(
                id=r.id,
                document_id=r.document_id,
                mode=r.mode,
                content=r.content,
                key_points=kp,
                word_count=len(r.content.split()),
                reading_time_saved_minutes=max(1, (doc.word_count - len(r.content.split())) // 220),
                provider_used=r.provider,
                model_used=r.model_id,
                created_at=r.created_at,
            )
        )
    return summaries


@agents_router.post(
    "/documents/{document_id}/ask",
    response_model=AskDocumentResponse,
    summary="Exact-Passage Q&A Verified by the Critic Agent (Grounded in Verbatim Citations)",
)
async def ask_document_with_critic(
    document_id: str,
    payload: AskDocumentRequest,
    db: Session = Depends(get_db),
) -> AskDocumentResponse:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found",
        )

    # 1. Retrieve candidate passages using Hybrid BM25 + Vector retriever
    ranked, _ = hybrid_search_passages(
        db,
        payload.question,
        top_k=payload.top_k,
        document_ids=[doc.id],
    )

    initial_state: AgentState = {
        "task_type": "ask_document",
        "document_id": doc.id,
        "document_title": doc.title,
        "document_text": doc.text_content,
        "question": payload.question,
        "retrieved_passages": ranked,
        "provider": payload.provider,
        "model": payload.model,
        "api_keys": _resolve_api_keys(db, payload.session_id, payload.api_keys),
        "iteration": 0,
    }

    result = await compiled_agent_graph.ainvoke(initial_state)

    answer = result.get("generated_answer") or result.get("final_output") or ""
    citations_data = result.get("citations") or []
    all_verified = bool(result.get("all_citations_verified", True))
    provider_used = result.get("provider_used", payload.provider or "openrouter")
    model_used = result.get("model_used", payload.model or "openrouter/free")

    citations_out = [RetrievedPassageSchema(**c) for c in citations_data]

    return AskDocumentResponse(
        document_id=doc.id,
        question=payload.question,
        answer=answer,
        citations=citations_out,
        all_citations_verified=all_verified,
        provider_used=provider_used,
        model_used=model_used,
    )


@agents_router.post(
    "/ask-context",
    response_model=AskContextResponse,
    summary="Contextual Excerpt Analyst: Explain, Critique, Define, or Analyze a Highlighted Reader Passage",
)
async def ask_contextual_excerpt(
    payload: AskContextRequest,
    db: Session = Depends(get_db),
) -> AskContextResponse:
    doc = db.get(Document, payload.document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{payload.document_id}' not found",
        )

    initial_state: AgentState = {
        "task_type": "ask_context",
        "document_id": doc.id,
        "document_title": doc.title,
        "document_text": doc.text_content,
        "selected_text": payload.selected_text,
        "start_char": payload.start_char,
        "end_char": payload.end_char,
        "action_or_question": payload.action_or_question,
        "provider": payload.provider,
        "model": payload.model,
        "api_keys": _resolve_api_keys(db, payload.session_id, payload.api_keys),
        "iteration": 0,
    }

    result = await compiled_agent_graph.ainvoke(initial_state)

    analysis = result.get("context_analysis") or result.get("final_output") or ""
    offset_verified = bool(result.get("offset_verified", True))
    provider_used = result.get("provider_used", payload.provider or "openrouter")
    model_used = result.get("model_used", payload.model or "openrouter/free")

    return AskContextResponse(
        document_id=doc.id,
        selected_text=payload.selected_text,
        action_or_question=payload.action_or_question,
        analysis=analysis,
        offset_verified=offset_verified,
        provider_used=provider_used,
        model_used=model_used,
    )


@agents_router.post(
    "/chat",
    summary="Interactive AI Chat with Live SSE Word-by-Word Streaming (text/event-stream) or JSON Response",
)
async def chat_interaction(
    payload: ChatMessageRequest,
    request: Request,
    stream: bool = Query(default=False, description="Set true or provide Accept: text/event-stream for SSE streaming"),
    db: Session = Depends(get_db),
) -> Any:
    # 1. Get or create thread
    thread = None
    if payload.thread_id:
        thread = db.get(ChatThread, payload.thread_id)
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ChatThread '{payload.thread_id}' not found",
            )
    else:
        if payload.document_id:
            doc = db.get(Document, payload.document_id)
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document '{payload.document_id}' not found",
                )
        thread = ChatThread(
            document_id=payload.document_id,
            title=f"Chat: {payload.message[:40]}...",
            provider=payload.provider or "openrouter",
            model_id=payload.model or "openrouter/free",
        )
        db.add(thread)
        db.flush()

    # 2. Record user message
    user_msg = ChatMessage(
        thread_id=thread.id,
        role="user",
        content=payload.message,
        provider=payload.provider,
        model_id=payload.model,
    )
    db.add(user_msg)
    db.commit()

    # Assemble conversation context
    history_stmt = select(ChatMessage).filter(ChatMessage.thread_id == thread.id).order_by(ChatMessage.created_at)
    history_rows = list(db.scalars(history_stmt).all())
    messages = [{"role": m.role, "content": m.content} for m in history_rows]

    # Add document context if attached
    if thread.document_id:
        doc = db.get(Document, thread.document_id)
        if doc and messages:
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": f"You are a research assistant conversing about the document '{doc.title}'. Ground your answers in this text:\n\n{doc.text_content[:3000]}",
                },
            )
    else:
        # Library-wide RAG context: retrieve relevant passages across ALL saved
        # documents so questions like "tell me about articles relating to rome" work.
        try:
            ranked, _ = hybrid_search_passages(
                db, payload.message, top_k=5, saved_only=True
            )
        except Exception:
            logger.exception(
                "Library-wide passage retrieval failed for chat; continuing without context"
            )
            ranked = []
        if ranked:
            snippets = "\n\n".join(
                f"- [{p.get('document_title', 'Untitled')}] "
                f"( passage {p.get('paragraph_index', '?')} ) {p.get('exact_quote', '')[:400]}"
                for p in ranked
            )
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": (
                        "You are a research assistant with search access to the user's saved reading library. "
                        "The most relevant passages from their library are:\n\n"
                        f"{snippets}\n\n"
                        "Answer using these passages and cite the [document title] each claim comes from. "
                        "If nothing in the library is relevant, say so plainly."
                    ),
                },
            )

    wants_stream = stream or "text/event-stream" in request.headers.get("accept", "").lower()

    if wants_stream:
        async def event_generator() -> AsyncIterator[str]:
            full_response_parts: List[str] = []
            async for chunk in stream_chat_completion(
                messages,
                provider=payload.provider,
                model=payload.model,
                api_keys=_resolve_api_keys(db, payload.session_id, payload.api_keys),
            ):
                full_response_parts.append(chunk)
                payload_json = json.dumps({"thread_id": thread.id, "token": chunk})
                yield f"data: {payload_json}\n\n"

            # Save assistant message to DB after stream completes
            full_response = "".join(full_response_parts)
            asst_msg = ChatMessage(
                thread_id=thread.id,
                role="assistant",
                content=full_response,
                provider=payload.provider,
                model_id=payload.model,
            )
            db.add(asst_msg)
            db.commit()
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # Standard JSON response
    initial_state: AgentState = {
        "task_type": "chat",
        "messages": messages,
        "provider": payload.provider,
        "model": payload.model,
        "api_keys": _resolve_api_keys(db, payload.session_id, payload.api_keys),
    }
    result = await compiled_agent_graph.ainvoke(initial_state)
    answer = result.get("final_output") or ""
    provider_used = result.get("provider_used", payload.provider or "openrouter")
    model_used = result.get("model_used", payload.model or "openrouter/free")

    asst_msg = ChatMessage(
        thread_id=thread.id,
        role="assistant",
        content=answer,
        provider=provider_used,
        model_id=model_used,
    )
    db.add(asst_msg)
    db.commit()
    db.refresh(asst_msg)

    return ChatMessageSchema(
        id=asst_msg.id,
        thread_id=thread.id,
        role=asst_msg.role,
        content=asst_msg.content,
        provider=asst_msg.provider,
        model_id=asst_msg.model_id,
        citations=[],
        created_at=asst_msg.created_at,
    )


@agents_router.get(
    "/chat/{thread_id}",
    response_model=ChatThreadResponse,
    summary="Get Chat Thread Details and Full Message History",
)
def get_chat_thread(
    thread_id: str,
    db: Session = Depends(get_db),
) -> ChatThreadResponse:
    thread = db.get(ChatThread, thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ChatThread '{thread_id}' not found",
        )

    messages_out = [
        ChatMessageSchema(
            id=m.id,
            thread_id=m.thread_id,
            role=m.role,
            content=m.content,
            provider=m.provider,
            model_id=m.model_id,
            citations=json.loads(m.citations_json or "[]"),
            created_at=m.created_at,
        )
        for m in thread.messages
    ]

    return ChatThreadResponse(
        id=thread.id,
        document_id=thread.document_id,
        title=thread.title,
        provider=thread.provider,
        model_id=thread.model_id,
        messages=messages_out,
        created_at=thread.created_at,
    )


@agents_router.delete(
    "/chat/{thread_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a Chat Thread and All Associated Messages",
)
def delete_chat_thread(
    thread_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    thread = db.get(ChatThread, thread_id)
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ChatThread '{thread_id}' not found",
        )
    db.delete(thread)
    db.commit()
    return {"deleted": True, "thread_id": thread_id}
