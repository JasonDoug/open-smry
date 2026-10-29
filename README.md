# Summary AI ⚡📚🤖

**Open-Source Agentic AI Reading, Summarizing & Verifiable Research Platform**  
*Patterned after [smry.ai](https://smry.ai) — built for Web, Desktop, Mobile, Browser Extensions, HTTP OpenAPI, and Model Context Protocol (MCP).*

[![License: MIT](https://img.shields.io/badge/License-MIT-indigo.svg)](./LICENSE)
[![OpenAPI 3.1](https://img.shields.io/badge/OpenAPI-3.1.0-emerald.svg)](./apps/api/src/openapi.mjs)
[![MCP Compatible](https://img.shields.io/badge/MCP-2024--11--05-purple.svg)](./packages/mcp-server/src/index.mjs)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)

---

## 🌟 Why Summary AI?

Save any **article, book, website, or YouTube video** and it gets **read, summarized, and filed for you**—with zero popups, ads, cookie banners, or soft paywalls. **Ask a question weeks later and get the answer verified with the exact source passage and character offsets.**

* **No Account Required**: Instant access via direct URL input on the web without mandatory sign-up.
* **Automatic Multi-Source Racing**: Concurrently queries **Direct Fetch**, **Wayback Machine**, **Google Cache / Archive mirrors**, and **Reader Proxy** to pull the most complete, unblocked version of an article.
* **Multi-LLM Intelligence**: Switch seamlessly between **Claude 3.7 Sonnet**, **GPT-4o**, **Gemini 2.5 Pro**, and a built-in zero-key extractive fallback engine.
* **Natural Voice TTS & Karaoke Highlighting**: 10 male/female voice profiles & accents with word-by-word real-time visual sync—click any word in the article to skip audio playback directly to that timestamp.
* **Agent-Native via MCP & REST OpenAPI**: Create and revoke `smry_live_...` API keys and connect Claude Desktop, Cursor, Antigravity, `curl`, or CI pipelines over MCP or HTTP REST.

---

## ✨ Complete Feature Matrix

### 1. Content Extraction & Reader Mode
* **Distraction-Free Reader**: Strips popups, advertisements, cookie banners, soft paywall overlays, and newsletter modals.
* **Automatic Source Selection**: Races multiple mirrors (`direct`, `wayback`, `googlecache`, `jina`) and scores completeness.
* **Reader Customization**: Dark, Light, and Sepia themes; adjustable font size (`14px–28px`), line spacing (`1.3–2.2`), page margins (`Narrow`, `Medium`, `Wide`), and **7 reader fonts** (`Inter`, `Georgia`, `Merriweather`, `Lora`, `JetBrains Mono`, `Atkinson Hyperlegible`, and **`OpenDyslexic`**).
* **Copy to LLMs**: One-click utility to export the stripped article into clean, structured Markdown ready for ChatGPT, Claude, or Gemini.
* **YouTube Video Transcripts**: Extracts timestamped readable transcripts from YouTube links (`youtube.com/watch`, `youtu.be`, `shorts`) for reading, summarizing, and Q&A.

### 2. AI Summarization, Streaming Chat & Exact-Passage RAG
* **Customizable Summaries**: Executive TL;DRs, Concise Bullet Points, Key Takeaways, Deep Research Briefs, or custom user prompts.
* **Model Selection**: Switch between **Claude**, **GPT**, and **Gemini**.
* **Streaming AI Chat**: Interactive conversational panel with real-time word-by-word SSE streaming.
* **Contextual "Ask AI"**: Highlight any passage in the reader to trigger targeted explanations, definitions, condensations, or critiques of just that excerpt.
* **Exact-Passage Library Q&A**: Ask a question later across all saved articles/books and get the answer with the **exact passage quote and character offsets**.

### 3. Text-to-Speech (TTS) & Karaoke Audio
* **Natural Voice Engine**: 10 distinct male/female voices across US, UK, Australian, Indian, European, and Canadian accents.
* **Karaoke-Style Word Sync**: Real-time word-by-word highlighting during narration; click any word in the text to jump directly to that audio timestamp.
* **Floating Playback Controls**: Adjustable speeds (`0.75x` to `2.0x`), play/pause, scrubber, and `±10s` skip controls.

### 4. Highlights, Annotations & Knowledge Management
* **Multi-Color Annotations**: 5 semantic highlight colors (`Yellow`, `Green`, `Blue`, `Purple`, `Coral`) + personal margin notes.
* **Annotations Sidebar & Filter**: Search highlights and notes, filter by color tag, and jump to passages.
* **Note-Taking App Exports**: One-click export to **Notion**, **Obsidian**, **Roam Research**, **Markdown**, or **JSON**.
* **Cloud Sync**: Cross-device JSON/state synchronization of saved articles, reading history, highlights, notes, and chat threads.

### 5. Multi-Platform & Agent Integration
* **Web Application** (`apps/web`): Instant no-account reader, AI assistant, Karaoke TTS player, and Agent hub.
* **Desktop Application** (`apps/desktop`): Cross-platform Tauri / Electron shell bundling the local API and MCP daemon.
* **Mobile Application** (`apps/mobile`): React Native / Expo app with OS Share-Sheet ingestion, OpenDyslexic support, and offline library cache.
* **Browser Extensions** (`apps/extension`): Manifest V3 (Chrome, Edge, Opera) + Firefox & Safari WebExtensions.
* **Model Context Protocol (MCP) Server** (`packages/mcp-server`) & **REST OpenAPI 3.1** (`apps/api`): Programmatic access for agents, scripts, `curl`, and CI with revocable API keys.

---

## 🏗️ Monorepo Structure

```text
summary-ai/
├── packages/
│   ├── shared/         # Domain schemas, 7 reader fonts, 10 TTS voices, PKM exporters & passage RAG indexer
│   ├── extractor/      # Multi-source mirror racer, paywall/ad sanitizer, YouTube transcripts & RSS parser
│   ├── ai/             # Claude/GPT/Gemini router, summaries, streaming SSE chat, Contextual Ask AI & Karaoke TTS
│   └── mcp-server/     # Model Context Protocol (MCP) JSON-RPC stdio server for external AI agents
├── apps/
│   ├── api/            # HTTP REST API server, OpenAPI 3.1 spec (/openapi.json), API keys & persistent store
│   ├── web/            # Distraction-Free Web Reader UI, Karaoke Audio Player & Annotations Drawer
│   ├── desktop/        # Cross-platform Desktop App controller & Tauri/Electron configuration
│   ├── mobile/         # Cross-platform Mobile App controller & Expo (iOS/Android) configuration
│   └── extension/      # Chromium (MV3), Firefox & Safari Browser Extensions
└── docs/
    └── ROADMAP.md      # Prioritized Feature Catalog (Rank 1–28) & Phased Sprint Plan (Sprints 1–8)
```

---

## 🚀 Quickstart

### 1. Install & Run Tests
```bash
pnpm install
npm test
```

### 2. Launch the Web Reader & REST OpenAPI Server
```bash
npm start
```
* **Web Reader UI**: [http://localhost:3333](http://localhost:3333)
* **Interactive OpenAPI Docs**: [http://localhost:3333/docs](http://localhost:3333/docs)
* **Raw OpenAPI 3.1 Spec**: [http://localhost:3333/openapi.json](http://localhost:3333/openapi.json)

### 3. Connect an External AI Agent via MCP
Add Summary AI to your Claude Desktop, Cursor, or Antigravity MCP configuration:
```json
{
  "mcpServers": {
    "summary-ai": {
      "command": "node",
      "args": ["/absolute/path/to/summary-ai/packages/mcp-server/src/index.mjs"]
    }
  }
}
```

### 4. Use the REST HTTP API from `curl`, Code, or CI
```bash
# 1. Create an Agent API Key
curl -X POST http://localhost:3333/api/v1/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "Research Agent"}'

# 2. Save an article, book, or website (automatically read, summarized & filed)
curl -X POST http://localhost:3333/api/v1/ingest \
  -H "Authorization: Bearer smry_live_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "model": "claude-3-7-sonnet", "summaryMode": "bullets"}'

# 3. Ask a question later and get the answer with the exact cited passage
curl -X POST http://localhost:3333/api/v1/library/ask \
  -H "Authorization: Bearer smry_live_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "What methodology was used?", "model": "claude-3-7-sonnet"}'
```

---

## 🗺️ Phased Development Sprints & Roadmap

See [docs/ROADMAP.md](./docs/ROADMAP.md) for the complete **28-item Prioritized Feature List** (sorted from most fundamental to least fundamental) and the **8 Phased Development Sprints**.

## 📄 License

Released under the [MIT License](./LICENSE).
