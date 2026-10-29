"""
Canonical Pydantic v2 Schemas & Platform Constants for Summary AI.
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


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
    preferred_provider: Literal["claude", "gpt", "gemini", "openrouter", "ollama"] = "claude"
    preferred_model: str = "claude-3-7-sonnet"
    preferred_voice_id: str = "aria-us-f"
    preferred_tts_speed: float = Field(default=1.0, ge=0.5, le=2.0)


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
    tags: List[str] = Field(default_factory=list)
    passages: List[PassageChunkSchema] = Field(default_factory=list)
    transcript_segments: Optional[List[TranscriptSegmentSchema]] = None
    created_at: datetime
    updated_at: datetime

