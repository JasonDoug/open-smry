"""
SQLAlchemy 2.0 ORM Models for Summary AI.
Covers anonymous/cloud sessions, documents (articles, books, websites, YouTube),
exact-offset passage chunks, summaries, multi-color annotations, chat threads,
reading history, RSS feeds, and SHA-256 hashed API keys.
"""
from datetime import datetime, timezone
from typing import List, Optional
import uuid
import secrets

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Base(DeclarativeBase):
    pass


class ReaderSession(Base):
    """
    Supports No-Account-Required instant access via anonymous session IDs,
    upgradable to cross-device Cloud Sync keys.
    Stores user reader customization preferences (7 fonts including OpenDyslexic,
    themes, font size, line spacing, margins, and preferred AI/TTS settings).
    """
    __tablename__ = "reader_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"sess_{secrets.token_hex(24)}")
    sync_token: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True, index=True)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Reader Customization Settings
    theme: Mapped[str] = mapped_column(String(24), default="dark", nullable=False)  # dark | light | sepia
    font_id: Mapped[str] = mapped_column(String(32), default="inter", nullable=False)  # 7 fonts incl. opendyslexic
    font_size_px: Mapped[int] = mapped_column(Integer, default=18, nullable=False)  # 14 - 32
    line_height: Mapped[float] = mapped_column(Float, default=1.75, nullable=False)  # 1.2 - 2.4
    margin_width: Mapped[str] = mapped_column(String(24), default="medium", nullable=False)  # narrow | medium | wide

    # AI & TTS Defaults
    preferred_provider: Mapped[str] = mapped_column(String(32), default="openrouter", nullable=False)
    preferred_model: Mapped[str] = mapped_column(String(128), default="openrouter/free", nullable=False)
    preferred_voice_id: Mapped[str] = mapped_column(String(32), default="aria-us-f", nullable=False)
    preferred_tts_speed: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    # Per-session API keys (overrides env vars for that session only)
    anthropic_api_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    openai_api_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    gemini_api_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    openrouter_api_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class Document(Base):
    """
    Unified content entity representing an extracted Web Article, Book (PDF/EPUB),
    Website, or YouTube Video Transcript.
    """
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: gen_id("doc"))
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    site_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    published_time: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    media_type: Mapped[str] = mapped_column(String(32), default="article", nullable=False)  # article | book | youtube | website | rss

    # Content representations
    excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    llm_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # Metrics & Source Racing Telemetry
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reading_time_minutes: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    stripped_elements_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_used: Mapped[str] = mapped_column(String(64), default="direct", nullable=False)
    source_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    source_attempts_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    # Library Filing & Tags
    saved_in_library: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    passages: Mapped[List["PassageChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="PassageChunk.paragraph_index"
    )
    summaries: Mapped[List["SummaryRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="SummaryRecord.created_at.desc()"
    )
    annotations: Mapped[List["Annotation"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Annotation.created_at"
    )
    chat_threads: Mapped[List["ChatThread"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class PassageChunk(Base):
    """
    Indexed passage chunk with exact character offsets (start_char, end_char)
    so questions asked weeks later return the answer with the exact source passage.
    """
    __tablename__ = "passage_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: gen_id("psg"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    paragraph_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    page_or_timestamp: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="passages")

    __table_args__ = (
        Index("ix_passage_doc_para", "document_id", "paragraph_index"),
    )


class SummaryRecord(Base):
    """
    Customizable AI summary generated for a Document.
    """
    __tablename__ = "summary_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: gen_id("sum"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(32), default="bullets", nullable=False)  # tldr | bullets | takeaways | executive | custom
    provider: Mapped[str] = mapped_column(String(32), default="claude", nullable=False)  # claude | gpt | gemini | openrouter | ollama
    model_id: Mapped[str] = mapped_column(String(128), default="claude-3-7-sonnet", nullable=False)
    custom_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    key_points_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    citations_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="summaries")


class Annotation(Base):
    """
    Multi-color text highlight and personal margin note anchored to exact offsets.
    """
    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: gen_id("ann"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(24), default="yellow", nullable=False)  # yellow | green | blue | purple | coral
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    start_char: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_char: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="annotations")


class ChatThread(Base):
    """
    Conversational AI thread scoped either to a specific Document or the entire Library.
    """
    __tablename__ = "chat_threads"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: gen_id("thr"))
    document_id: Mapped[Optional[str]] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(256), default="Research Conversation", nullable=False)
    provider: Mapped[str] = mapped_column(String(32), default="claude", nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), default="claude-3-7-sonnet", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[Optional["Document"]] = relationship(back_populates="chat_threads")
    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )


class ChatMessage(Base):
    """
    Individual message in a ChatThread, storing exact passage citations when role='assistant'.
    """
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: gen_id("msg"))
    thread_id: Mapped[str] = mapped_column(ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(24), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    model_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    citations_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    thread: Mapped["ChatThread"] = relationship(back_populates="messages")


class ReadingHistory(Base):
    """
    Chronological log of extracted and read articles, books, websites, and YouTube videos.
    """
    __tablename__ = "reading_history"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: gen_id("hist"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_used: Mapped[str] = mapped_column(String(64), default="direct", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)


class RssFeed(Base):
    """
    Subscribed RSS/Atom feed for automated extraction, summarization, and library filing.
    """
    __tablename__ = "rss_feeds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: gen_id("feed"))
    feed_url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    site_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    auto_summarize: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    items: Mapped[List["RssFeedItem"]] = relationship(
        back_populates="feed", cascade="all, delete-orphan", order_by="RssFeedItem.published_at.desc()"
    )


class RssFeedItem(Base):
    """
    Individual item discovered in an RssFeed.
    """
    __tablename__ = "rss_feed_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: gen_id("fitem"))
    feed_id: Mapped[str] = mapped_column(ForeignKey("rss_feeds.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[Optional[str]] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    guid: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    summary_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    feed: Mapped["RssFeed"] = relationship(back_populates="items")


class ApiKey(Base):
    """
    SHA-256 hashed API Key credential (smry_live_...) for external AI agents, scripts, curl, and CI.
    """
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: gen_id("key"))
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    scopes_json: Mapped[str] = mapped_column(Text, default='["read","write","extract","summarize","mcp"]', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
