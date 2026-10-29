# Summary AI — Sprint Review, Testing & Bug Tracker

> [!IMPORTANT]
> **Mandatory Post-Sprint Review & Bug Tracking Protocol:**
> After **every single sprint**, we pause at a strict review gate:
> 1. **Automated Testing:** Run the sprint's automated test suite (`pytest` / `node --test`).
> 2. **Live Demo for Your Hands-On Testing:** Launch the live server/UI and give you exact URLs and commands so you can test the sprint deliverables yourself.
> 3. **Interactive Review Conversation:** We discuss your findings, UX impressions, and architectural feedback.
> 4. **Bug & Adjustment Logging:** Every change or bug you identify is logged below as `BUG-001`, `ADJ-001`, etc., implemented, and re-tested.
> 5. **User Sign-Off:** We only advance to the next sprint once you sign off on the current sprint.

---

## 📊 9-Sprint Progression & Sign-Off Matrix

| Sprint | Core Practice & Focus | Features (Rank) | Test Status | Demo & Review Status | User Sign-Off |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Sprint 1** | **Polyglot Monorepo, SQLAlchemy/SQLite DB, FastAPI OpenAPI 3.1 Core & OSS Governance** | #1, #2, #3 | ✅ **11/11 Passing** (`6 pytest` + `5 TS`) | ✅ Completed | ✅ **Signed Off** |
| **Sprint 2** | **Async Multi-Source Racer (`httpx`), Sanitizer (`trafilatura`/`BS4`), YouTube & Books (PDF/EPUB)** | #4, #5, #6, #9, #10 | ✅ **15/15 Passing** (`10 pytest` + `5 TS`) | 🟢 **In Review Now** (`http://localhost:8000`) | ⏳ Awaiting Your Sign-Off |
| **Sprint 3** | **Exact-Offset Passage Chunker, Hybrid RAG (`rank-bm25` + Vectors) & Library Filing** | #7, #8, #28 | ⏸️ Queued Next | ⏸️ Queued | ⏳ Pending |
| **Sprint 4** | **LangGraph Multi-Agent System (Claude/GPT/Gemini/OpenRouter/Ollama), Critic & Streaming Chat** | #11–#16 | ⏸️ Queued | ⏸️ Queued | ⏳ Pending |
| **Sprint 5** | **Distraction-Free React/TS Web Reader, Source Switcher & 7 Fonts (incl. OpenDyslexic)** | #17, #18 | ⏸️ Queued | ⏸️ Queued | ⏳ Pending |
| **Sprint 6** | **5-Color Highlights, Margin Notes Drawer & PKM Exports (Notion, Obsidian, Roam, MD, JSON)** | #19, #20, #21 | ⏸️ Queued | ⏸️ Queued | ⏳ Pending |
| **Sprint 7** | **Natural Voice Neural TTS (`edge-tts`, 10 Voices/Accents) & Karaoke WordBoundary Sync** | #22, #23, #24 | ⏸️ Queued | ⏸️ Queued | ⏳ Pending |
| **Sprint 8** | **Agentic Ecosystem: SHA-256 API Keys (`smry_live_...`), RSS Auto-Ingest & `FastMCP` Server** | #25, #26, #27 | ⏸️ Queued | ⏸️ Queued | ⏳ Pending |
| **Sprint 9** | **Multi-Platform Clients: Desktop (`Tauri v2`), Mobile (`Expo`), Browser Extensions & Docker** | #29, #30, #31, #32 | ⏸️ Queued | ⏸️ Queued | ⏳ Pending |

---

## 🐛 Active Bugs & Adjustment Tracking Log

| ID | Sprint | Type | Severity | Description / Requested Adjustment | Status | Resolution / Commit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ADJ-001` | Plan | Architecture | High | Upgrade backend to full-scale Python 3.13 + **LangGraph** multi-agent system + FastAPI + Hybrid RAG + Neural TTS + `FastMCP`. | ✅ Resolved | Implemented in Sprint 1 Foundation |
| `ADJ-002` | Plan | Feature | High | Add first-class support for **Local AI (Ollama auto-discovery, LM Studio, llama.cpp, vLLM, local embeddings)** and **OpenRouter (`openrouter.ai`)**. | ✅ Resolved | Configured in `config.py`, `domain.py` & `/api/v1/models/providers` |
| `ADJ-003` | Process | Workflow | High | Enforce strict post-sprint testing, live user demo/review, interactive conversation, and bug/adjustment tracking before advancing between sprints. | ✅ Active | Enforced at Sprint Review Gates |
| `BUG-001` | Sprint 1 | Bug | Medium | `GET http://localhost:8000//api/v1/health` returns `404 Not Found` due to duplicate/consecutive slashes not being normalized before Starlette route matching. | ✅ Fixed & Verified | Added `NormalizeSlashMiddleware` in `backend/app/main.py` + `test_double_slash_path_normalization_bug_001` |
| `BUG-002` | Sprint 1 | Bug | Medium | Importing `/openapi.json` into Bruno produced `//` in URLs because FastAPI omitted a `servers` entry without a trailing slash (causing Bruno's `{{baseUrl}}` to default to `/` or include a trailing `/`). | ✅ Fixed & Verified | Added explicit `servers=[{"url": "http://localhost:8000"}]` (no trailing slash) in `backend/app/main.py` + test assertion in `test_openapi_3_1_and_health` |
| `ADJ-004` | Sprint 1 | Enhancement | Medium | Add the free OpenRouter router (`openrouter/free`) to `/api/v1/models/providers` and preset models. | ✅ Fixed & Verified | Added `openrouter/free` to `AI_MODELS`, `AI_PROVIDERS`, `config.py`, and `/api/v1/models/providers` |
