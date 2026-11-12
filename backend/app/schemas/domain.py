"""
Canonical Pydantic v2 Schemas & Platform Constants for Summary AI.
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


READER_FONTS: List[Dict[str, str]] = [
    {
        "id": "inter",
        "name": "Inter",
        "family": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        "category": "sans-serif",
        "description": "Crisp modern sans-serif for screen legibility",
    },
    {
        "id": "georgia",
        "name": "Georgia",
        "family": "Georgia, 'Times New Roman', serif",
        "category": "serif",
        "description": "Classic editorial serif with generous x-height",
    },
    {
        "id": "merriweather",
        "name": "Merriweather",
        "family": "'Merriweather', Georgia, serif",
        "category": "serif",
        "description": "Warm long-form book serif designed for digital screens",
    },
    {
        "id": "lora",
        "name": "Lora",
        "family": "'Lora', Georgia, serif",
        "category": "serif",
        "description": "Contemporary calligraphic serif ideal for essays",
    },
    {
        "id": "jetbrains-mono",
        "name": "JetBrains Mono",
        "family": "'JetBrains Mono', 'Fira Code', monospace",
        "category": "monospace",
        "description": "Developer-friendly monospace for technical articles",
    },
    {
        "id": "atkinson",
        "name": "Atkinson Hyperlegible",
        "family": "'Atkinson Hyperlegible', sans-serif",
        "category": "accessibility",
        "description": "High-distinction letterforms for low-vision accessibility",
    },
    {
        "id": "opendyslexic",
        "name": "OpenDyslexic",
        "family": "'OpenDyslexic', 'Comic Sans MS', sans-serif",
        "category": "accessibility",
        "description": "Weighted bottoms to prevent letter rotation and aid dyslexic readers",
    },
]

HIGHLIGHT_COLORS: List[Dict[str, str]] = [
    {"id": "yellow", "label": "Amber Insight", "hex": "#facc15", "bg": "rgba(250, 204, 21, 0.28)"},
    {"id": "green", "label": "Emerald Fact", "hex": "#34d399", "bg": "rgba(52, 211, 153, 0.28)"},
    {"id": "blue", "label": "Sky Reference", "hex": "#38bdf8", "bg": "rgba(56, 189, 248, 0.28)"},
    {"id": "purple", "label": "Violet Concept", "hex": "#c084fc", "bg": "rgba(192, 132, 252, 0.28)"},
    {"id": "coral", "label": "Coral Question", "hex": "#fb7185", "bg": "rgba(251, 113, 133, 0.28)"},
]

EXTRACTION_SOURCES: List[Dict[str, str]] = [
    {
        "id": "auto",
        "name": "Auto Race (Fastest Unblocked)",
        "description": "Concurrently races Direct Fetch, Wayback Machine, Google Cache, and Reader Proxy mirrors",
    },
    {"id": "direct", "name": "Direct Fetch", "description": "Fetches straight from the origin server"},
    {"id": "wayback", "name": "Wayback Machine", "description": "Queries Internet Archive snapshots"},
    {"id": "googlecache", "name": "Archive / Cache Mirror", "description": "Queries cached text-only mirrors"},
    {"id": "jina", "name": "Reader Proxy Mirror", "description": "Fetches via clean Markdown reader proxy"},
]

SUMMARY_MODES: List[Dict[str, str]] = [
    {"id": "tldr", "name": "Executive TL;DR", "description": "2-3 sentence high-impact synthesis"},
    {"id": "bullets", "name": "Concise Bullet Points", "description": "Scannable bulleted breakdown of core points"},
    {"id": "takeaways", "name": "Key Takeaways", "description": "Actionable insights, thesis, and implications"},
    {"id": "executive", "name": "Deep Research Brief", "description": "Structured briefing with context, arguments, and counterpoints"},
    {"id": "custom", "name": "Custom Prompt", "description": "Driven by your own custom instructions"},
]

AI_PROVIDERS: List[Dict[str, str]] = [
    {
        "id": "claude",
        "name": "Anthropic Claude",
        "type": "cloud",
        "default_model": "claude-3-7-sonnet-latest",
        "description": "Anthropic Claude models for nuanced synthesis and citation verification",
    },
    {
        "id": "gpt",
        "name": "OpenAI GPT",
        "type": "cloud",
        "default_model": "gpt-4o",
        "description": "OpenAI GPT & reasoning models for structured executive summaries",
    },
    {
        "id": "gemini",
        "name": "Google Gemini",
        "type": "cloud",
        "default_model": "gemini-2.5-pro",
        "description": "Google Gemini models with 1M+ context window for whole books & transcripts",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "type": "aggregator",
        "default_model": "openrouter/free",
        "description": "Unified API gateway including the free auto-router (openrouter/free), DeepSeek, Qwen, Llama, Claude, GPT & Gemini",
    },
    {
        "id": "ollama",
        "name": "Local AI (Ollama / LM Studio / vLLM)",
        "type": "local",
        "default_model": "llama3.2",
        "description": "100% private local inference & local embeddings with live model auto-discovery",
    },
]

AI_MODELS: List[Dict[str, str]] = [
    {
        "id": "claude-3-7-sonnet",
        "provider": "claude",
        "name": "Claude 3.7 Sonnet",
        "badge": "Anthropic",
        "description": "Nuanced synthesis, deep analytical reasoning, and faithful citations",
    },
    {
        "id": "gpt-4o",
        "provider": "gpt",
        "name": "GPT-4o",
        "badge": "OpenAI",
        "description": "Fast multimodal reasoning and structured executive summaries",
    },
    {
        "id": "gemini-2.5-pro",
        "provider": "gemini",
        "name": "Gemini 2.5 Pro",
        "badge": "Google",
        "description": "Long-context book & research synthesis with rapid recall",
    },
    {
        "id": "openrouter/free",
        "provider": "openrouter",
        "name": "OpenRouter Free Router (openrouter/free)",
        "badge": "OpenRouter Free",
        "description": "Automatically routes requests to the best available free models on OpenRouter",
    },
    {
        "id": "openrouter/deepseek/deepseek-r1",
        "provider": "openrouter",
        "name": "DeepSeek R1 (via OpenRouter)",
        "badge": "OpenRouter",
        "description": "Open-weights frontier reasoning model routed via OpenRouter",
    },
    {
        "id": "openrouter/meta-llama/llama-3.3-70b-instruct",
        "provider": "openrouter",
        "name": "Llama 3.3 70B Instruct (via OpenRouter)",
        "badge": "OpenRouter",
        "description": "High-speed open-weights synthesis via OpenRouter",
    },
    {
        "id": "ollama/llama3.2",
        "provider": "ollama",
        "name": "Llama 3.2 (Local Ollama)",
        "badge": "Local AI",
        "description": "Runs 100% locally via Ollama with zero external API calls",
    },
    {
        "id": "ollama/qwen2.5:14b",
        "provider": "ollama",
        "name": "Qwen 2.5 14B (Local Ollama)",
        "badge": "Local AI",
        "description": "High-accuracy local research & RAG model on Ollama",
    },
]

TTS_VOICES: List[Dict[str, Any]] = [
    {"id": "aria-us-f", "name": "Aria", "gender": "female", "accent": "US English", "lang": "en-US", "edge_voice": "en-US-AriaNeural"},
    {"id": "marcus-us-m", "name": "Marcus", "gender": "male", "accent": "US English", "lang": "en-US", "edge_voice": "en-US-GuyNeural"},
    {"id": "elena-uk-f", "name": "Elena", "gender": "female", "accent": "British English", "lang": "en-GB", "edge_voice": "en-GB-SoniaNeural"},
    {"id": "arthur-uk-m", "name": "Arthur", "gender": "male", "accent": "British English", "lang": "en-GB", "edge_voice": "en-GB-RyanNeural"},
    {"id": "chloe-au-f", "name": "Chloe", "gender": "female", "accent": "Australian English", "lang": "en-AU", "edge_voice": "en-AU-NatashaNeural"},
    {"id": "liam-au-m", "name": "Liam", "gender": "male", "accent": "Australian English", "lang": "en-AU", "edge_voice": "en-AU-WilliamNeural"},
    {"id": "kavya-in-f", "name": "Kavya", "gender": "female", "accent": "Indian English", "lang": "en-IN", "edge_voice": "en-IN-NeerjaNeural"},
    {"id": "rohan-in-m", "name": "Rohan", "gender": "male", "accent": "Indian English", "lang": "en-IN", "edge_voice": "en-IN-PrabhatNeural"},
    {"id": "claire-eu-f", "name": "Claire", "gender": "female", "accent": "Irish / European English", "lang": "en-IE", "edge_voice": "en-IE-EmilyNeural"},
    {"id": "mateo-ca-m", "name": "Mateo", "gender": "male", "accent": "North American Broadcast", "lang": "en-CA", "edge_voice": "en-CA-LiamNeural"},
]


class ReaderSettingsSchema(BaseModel):
    theme: Literal["dark", "light", "sepia"] = "dark"
    font_id: str = Field(default="inter", description="One of the 7 reader fonts including opendyslexic")
    font_size_px: int = Field(default=18, ge=14, le=32)
    line_height: float = Field(default=1.75, ge=1.2, le=2.4)
    margin_width: Literal["narrow", "medium", "wide"] = "medium"
    preferred_provider: Literal["claude", "gpt", "gemini", "openrouter", "ollama"] = "openrouter"
    preferred_model: str = "openrouter/free"
    preferred_voice_id: str = "aria-us-f"
    preferred_tts_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    # Per-session API keys (masked on read; only presence is returned)
    has_anthropic_key: bool = False
    has_openai_key: bool = False
    has_gemini_key: bool = False
    has_openrouter_key: bool = False


class ReaderSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "theme": "dark",
                "font_id": "opendyslexic",
                "font_size_px": 20,
                "line_height": 1.8,
                "margin_width": "medium",
                "preferred_provider": "openrouter",
                "preferred_model": "openrouter/free",
                "preferred_voice_id": "aria-us-f",
                "preferred_tts_speed": 1.0,
                "openrouter_api_key": "sk-or-v1-...",
            }
        }
    )
    theme: Optional[Literal["dark", "light", "sepia"]] = None
    font_id: Optional[str] = None
    font_size_px: Optional[int] = Field(default=None, ge=14, le=32)
    line_height: Optional[float] = Field(default=None, ge=1.2, le=2.4)
    margin_width: Optional[Literal["narrow", "medium", "wide"]] = None
    preferred_provider: Optional[Literal["claude", "gpt", "gemini", "openrouter", "ollama"]] = None
    preferred_model: Optional[str] = None
    preferred_voice_id: Optional[str] = None
    preferred_tts_speed: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None


class AnonymousSessionResponse(BaseModel):
    session_id: str
    is_anonymous: bool = True
    no_account_required: bool = True
    sync_token: Optional[str] = None
    settings: ReaderSettingsSchema
    created_at: datetime
    updated_at: datetime


class PlatformMetaResponse(BaseModel):
    name: str = "Summary AI"
    version: str = "1.0.0"
    no_account_required: bool = True
    reader_fonts: List[Dict[str, str]]
    highlight_colors: List[Dict[str, str]]
    extraction_sources: List[Dict[str, str]]
    summary_modes: List[Dict[str, str]]
    ai_providers: List[Dict[str, str]]
    ai_models: List[Dict[str, str]]
    tts_voices: List[Dict[str, Any]]
    default_reader_settings: ReaderSettingsSchema


# ============================================================================
# Sprint 2 Schemas: Content Extraction, Multi-Source Racing, YouTube & Books
# ============================================================================


class SourceAttemptSchema(BaseModel):
    source: str
    status: str
    word_count: int
    score: float
    latency_ms: int
    selected: bool


class PassageChunkSchema(BaseModel):
    id: Optional[str] = None
    paragraph_index: int
    chapter_title: Optional[str] = None
    page_or_timestamp: Optional[str] = None
    start_char: int
    end_char: int
    text: str


class TranscriptSegmentSchema(BaseModel):
    index: int
    start_sec: float
    duration_sec: float
    timestamp: str
    text: str


class ExtractUrlRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://example.com",
                "source": "auto",
                "save_to_library": True,
                "tags": ["web", "reader"],
            }
        }
    )
    url: str = Field(default="https://example.com", description="Target article, website, or YouTube URL")
    source: Literal["auto", "direct", "wayback", "googlecache", "jina"] = Field(
        default="auto",
        description="Mirror selection mode: 'auto' races all mirrors in parallel",
    )
    raw_html: Optional[str] = Field(
        default=None,
        description="Optional raw HTML override (e.g., from Browser Extension active tab DOM)",
    )
    title_override: Optional[str] = None
    save_to_library: bool = True
    tags: List[str] = Field(default_factory=list)


class ExtractYouTubeRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "languages": ["en"],
                "save_to_library": True,
                "tags": ["youtube", "video"],
            }
        }
    )
    url: str = Field(
        default="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        description="YouTube watch, short, or youtu.be link",
    )
    languages: List[str] = Field(default_factory=lambda: ["en", "en-US"])
    save_to_library: bool = True
    tags: List[str] = Field(default_factory=lambda: ["youtube"])


class ExtractBookRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Designing Agentic Research Systems",
                "author": "Dr. Ada Lovelace",
                "format": "markdown",
                "text_content": (
                    "# Chapter 1: Distraction-Free Reading\n\n"
                    "Modern research requires stripping popups, ads, and soft paywalls so readers can focus on primary sources.\n\n"
                    "# Chapter 2: Verifiable Passage Citations\n\n"
                    "Indexing every paragraph by exact start_char and end_char offsets eliminates hallucinated references."
                ),
                "save_to_library": True,
                "tags": ["book", "agentic-ai"],
            }
        }
    )
    title: str = Field(default="Uploaded Book", description="Book or document title")
    author: Optional[str] = None
    source_url: str = Field(default="book://library-upload")
    format: Literal["pdf", "epub", "markdown", "text"] = "markdown"
    file_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded PDF or EPUB binary when format is 'pdf' or 'epub'",
    )
    text_content: Optional[str] = Field(
        default=None,
        description="Raw Markdown or plain-text book content when format is 'markdown' or 'text'",
    )
    save_to_library: bool = True
    tags: List[str] = Field(default_factory=lambda: ["book"])


class CopyToLlmResponse(BaseModel):
    document_id: str
    title: str
    url: str
    source_used: str
    word_count: int
    llm_markdown: str


class ExtractedDocumentResponse(BaseModel):
    id: str
    url: str
    canonical_url: Optional[str] = None
    image_url: Optional[str] = None
    title: str
    author: Optional[str] = None
    site_name: Optional[str] = None
    published_time: Optional[str] = None
    media_type: str
    excerpt: Optional[str] = None
    content_html: str
    text_content: str
    llm_markdown: str
    word_count: int
    reading_time_minutes: int
    stripped_elements_count: int
    source_used: str
    source_score: float
    source_attempts: List[SourceAttemptSchema] = Field(default_factory=list)
    saved_in_library: bool
    paywall_detected: bool = False
    tags: List[str] = Field(default_factory=list)
    passages: List[PassageChunkSchema] = Field(default_factory=list)
    transcript_segments: Optional[List[TranscriptSegmentSchema]] = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Sprint 3 Schemas: Hybrid RAG Search, Exact Passage Verification,
# Saved Library, Reading History & Cross-Device Cloud Sync
# ============================================================================


class LibraryUpdateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Updated Research Article Title",
                "saved_in_library": True,
                "tags": ["research", "rag", "favorite"],
            }
        }
    )
    title: Optional[str] = None
    saved_in_library: Optional[bool] = None
    tags: Optional[List[str]] = None


class LibraryItemSummarySchema(BaseModel):
    id: str
    url: str
    title: str
    author: Optional[str] = None
    site_name: Optional[str] = None
    media_type: str
    image_url: Optional[str] = None
    excerpt: Optional[str] = None
    word_count: int
    reading_time_minutes: int
    source_used: str
    saved_in_library: bool
    tags: List[str] = Field(default_factory=list)
    passage_count: int = 0
    created_at: datetime
    updated_at: datetime


class LibraryListResponse(BaseModel):
    total: int
    items: List[LibraryItemSummarySchema]


class HybridSearchRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "exact start_char and end_char offsets",
                "top_k": 5,
                "document_ids": None,
                "tag": None,
                "media_type": None,
                "saved_only": False,
            }
        }
    )
    query: str = Field(
        default="exact start_char and end_char offsets",
        min_length=1,
        description="Search query evaluated via Hybrid BM25 + Dense Vector Cosine Similarity + RRF",
    )
    top_k: int = Field(default=5, ge=1, le=25)
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional filter restricting search to specific document IDs",
    )
    tag: Optional[str] = Field(
        default=None,
        description="Optional tag filter (e.g., 'book', 'youtube', 'web')",
    )
    media_type: Optional[str] = Field(
        default=None,
        description="Optional media_type filter ('article', 'book', 'youtube')",
    )
    saved_only: bool = Field(
        default=False,
        description="If true, only search documents marked saved_in_library=True",
    )


class RetrievedPassageSchema(BaseModel):
    rank: int
    passage_id: str
    document_id: str
    document_title: str
    document_url: str
    media_type: str
    paragraph_index: int
    chapter_title: Optional[str] = None
    page_or_timestamp: Optional[str] = None
    start_char: int
    end_char: int
    exact_quote: str
    offset_verified: bool
    bm25_score: float
    vector_score: float
    hybrid_score: float


class HybridSearchResponse(BaseModel):
    query: str
    total_candidates_scanned: int
    returned_count: int
    all_offsets_verified: bool
    passages: List[RetrievedPassageSchema]


class ReindexLibraryRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "provider": "deterministic",
                "ollama_model": "nomic-embed-text-v2-moe:latest",
                "document_ids": None,
            }
        }
    )
    provider: Literal["deterministic", "ollama"] = Field(
        default="deterministic",
        description=(
            "Embedding provider: 'deterministic' (256-dim local hashing) or 'ollama' (live local Ollama /api/embed). "
            "Note: Ollama vectors are persisted in PassageChunk.embedding_json. Hybrid search currently uses 256-dim "
            "deterministic embeddings for synchronous low-latency query ranking, falling back if stored dimensions differ."
        ),
    )
    ollama_model: str = Field(
        default="nomic-embed-text-v2-moe:latest",
        description="Local Ollama embedding model name when provider='ollama'",
    )
    document_ids: Optional[List[str]] = None


class ReindexLibraryResponse(BaseModel):
    provider_used: str
    documents_indexed: int
    passages_indexed: int
    embedding_dimension: int


class ReadingHistoryItemSchema(BaseModel):
    id: str
    document_id: str
    title: str
    url: str
    source_used: str
    word_count: int
    last_read_at: datetime


class ReadingHistoryResponse(BaseModel):
    total: int
    items: List[ReadingHistoryItemSchema]


class CloudSyncImportRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "demo-sync-session",
                "settings": {
                    "theme": "sepia",
                    "font_id": "merriweather",
                    "font_size_px": 20,
                    "line_height": 1.8,
                    "margin_width": "medium",
                    "preferred_provider": "openrouter",
                    "preferred_model": "openrouter/free",
                    "preferred_voice_id": "aria-us-f",
                    "preferred_tts_speed": 1.0,
                },
                "saved_document_ids": [],
            }
        }
    )
    session_id: str = Field(default="demo-sync-session")
    settings: Optional[ReaderSettingsSchema] = None
    saved_document_ids: List[str] = Field(default_factory=list)


class CloudSyncSnapshotResponse(BaseModel):
    sync_version: str = "1.0"
    session_id: str
    settings: ReaderSettingsSchema
    library_count: int
    history_count: int
    library_items: List[LibraryItemSummarySchema]
    reading_history: List[ReadingHistoryItemSchema]
    exported_at: datetime


# ============================================================================
# Sprint 4 Schemas: LangGraph Multi-Agent Orchestration, Multi-LLM Router,
# 5-Mode Summaries, Verifiable Q&A Critic, Context Analyst & Streaming Chat
# ============================================================================


class SummarizeRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "demo_doc_id",
                "mode": "bullets",
                "custom_prompt": None,
                "provider": "openrouter",
                "model": "openrouter/free",
            }
        }
    )
    document_id: str = Field(description="Target Document ID to summarize")
    mode: Literal["tldr", "bullets", "takeaways", "executive", "custom"] = Field(
        default="bullets",
        description="Summarization mode: 'tldr' (executive synthesis), 'bullets' (key claims), 'takeaways' (actionable implications), 'executive' (deep research brief), 'custom' (user prompt)",
    )
    custom_prompt: Optional[str] = Field(
        default=None,
        description="Custom prompt instructions when mode='custom'",
    )
    provider: Optional[Literal["claude", "gpt", "gemini", "openrouter", "ollama"]] = Field(
        default=None,
        description="LLM provider: 'claude', 'gpt', 'gemini', 'openrouter', or 'ollama'",
    )
    model: Optional[str] = Field(
        default=None,
        description="Model ID (e.g., 'openrouter/free', 'claude-3-7-sonnet', 'gpt-4o', 'qwen2.5:7b')",
    )
    api_keys: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional per-request API key overrides keyed by provider (anthropic, openai, gemini, openrouter)",
    )
    session_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional reader session ID whose persisted provider API keys should be "
            "used for this request (per-request api_keys take precedence)"
        ),
    )

    @model_validator(mode="after")
    def validate_custom_prompt(self) -> "SummarizeRequest":
        if self.mode == "custom" and (not self.custom_prompt or not self.custom_prompt.strip()):
            raise ValueError("custom_prompt is required and cannot be empty when mode='custom'.")
        return self


class SummaryResponse(BaseModel):
    id: str
    document_id: str
    mode: str
    content: str
    key_points: List[str] = Field(default_factory=list)
    word_count: int
    reading_time_saved_minutes: int
    provider_used: str
    model_used: str
    created_at: datetime


class AskDocumentRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "demo_doc_id",
                "question": "What is the core argument regarding verifiable passage citations?",
                "top_k": 5,
                "provider": "openrouter",
                "model": "openrouter/free",
            }
        }
    )
    document_id: str = Field(description="Document ID to query")
    question: str = Field(
        min_length=1,
        description="Research inquiry to answer with verbatim passage citations",
    )
    top_k: int = Field(default=5, ge=1, le=20)
    provider: Optional[Literal["claude", "gpt", "gemini", "openrouter", "ollama"]] = None
    model: Optional[str] = None
    api_keys: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional per-request API key overrides keyed by provider (anthropic, openai, gemini, openrouter)",
    )
    session_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional reader session ID whose persisted provider API keys should be "
            "used for this request (per-request api_keys take precedence)"
        ),
    )


class AskDocumentResponse(BaseModel):
    document_id: str
    question: str
    answer: str
    citations: List[RetrievedPassageSchema] = Field(default_factory=list)
    all_citations_verified: bool
    provider_used: str
    model_used: str


class AskContextRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "demo_doc_id",
                "selected_text": "Indexing every paragraph by exact start_char and end_char offsets eliminates hallucinated references.",
                "start_char": 100,
                "end_char": 213,
                "action_or_question": "explain",
                "provider": "openrouter",
                "model": "openrouter/free",
            }
        }
    )
    document_id: str = Field(description="Document ID containing the highlighted text")
    selected_text: str = Field(
        min_length=1,
        description="Highlighted text passage from the reader interface",
    )
    start_char: Optional[int] = Field(default=None, description="Exact start character index")
    end_char: Optional[int] = Field(default=None, description="Exact end character index")
    action_or_question: str = Field(
        default="explain",
        description="'explain' | 'critique' | 'define' | or any custom question regarding this excerpt",
    )
    provider: Optional[Literal["claude", "gpt", "gemini", "openrouter", "ollama"]] = None
    model: Optional[str] = None
    api_keys: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional per-request API key overrides keyed by provider (anthropic, openai, gemini, openrouter)",
    )
    session_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional reader session ID whose persisted provider API keys should be "
            "used for this request (per-request api_keys take precedence)"
        ),
    )


class AskContextResponse(BaseModel):
    document_id: str
    selected_text: str
    action_or_question: str
    analysis: str
    offset_verified: bool
    provider_used: str
    model_used: str


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "thread_id": None,
                "document_id": "demo_doc_id",
                "message": "Summarize the primary conclusions and cite the exact passages.",
                "provider": "openrouter",
                "model": "openrouter/free",
            }
        }
    )
    thread_id: Optional[str] = Field(default=None, description="Existing thread ID or None to create a new thread")
    document_id: Optional[str] = Field(default=None, description="Optional document ID context")
    message: str = Field(
        min_length=1,
        description="User message content",
    )
    provider: Optional[Literal["claude", "gpt", "gemini", "openrouter", "ollama"]] = None
    model: Optional[str] = None
    api_keys: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional per-request API key overrides keyed by provider (anthropic, openai, gemini, openrouter)",
    )
    session_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional reader session ID whose persisted provider API keys should be "
            "used for this request (per-request api_keys take precedence)"
        ),
    )


class ChatMessageSchema(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    provider: Optional[str] = None
    model_id: Optional[str] = None
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class ChatThreadResponse(BaseModel):
    id: str
    document_id: Optional[str] = None
    title: str
    provider: str
    model_id: str
    messages: List[ChatMessageSchema] = Field(default_factory=list)
    created_at: datetime



