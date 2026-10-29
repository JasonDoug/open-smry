# Contributing to Summary AI

Thank you for contributing to **Summary AI**! Our goal is to build the best open-source agentic AI reading, summarizing, and research suite across Web, Desktop, Mobile, Browser Extensions, REST OpenAPI, and Model Context Protocol (MCP).

## Architecture Overview

This repository is a modular monorepo organized into:

* `packages/shared` — Shared domain models, validation schemas, reader themes/fonts (including OpenDyslexic), and PKM export formatters (Notion, Obsidian, Roam Research, Markdown, JSON).
* `packages/extractor` — Multi-source racing engine (Direct, Wayback Machine, Google Cache, Archive mirrors), distraction/paywall stripper, Markdown converter ("Copy to LLMs"), YouTube transcript extractor, and RSS/Atom feed parser.
* `packages/ai` — Multi-provider LLM router (Claude, GPT, Gemini, and zero-key extractive fallback), customizable summaries, streaming chat, contextual "Ask AI", exact-passage RAG retrieval, and Natural Voice TTS with word-level Karaoke sync.
* `packages/mcp-server` — Model Context Protocol (MCP) server for Claude Desktop, Cursor, Antigravity, and external agents.
* `apps/api` — REST HTTP server with OpenAPI 3.1 spec (`/openapi.json`), API key management (`/api/v1/keys`), library filing, RSS management, and cross-device sync.
* `apps/web` — Distraction-free Web Reader, AI Chat, Karaoke TTS Player, Multi-color Highlighter, and Agent/API Keys Hub.
* `apps/desktop` — Cross-platform Desktop App (Tauri / Electron).
* `apps/mobile` — Cross-platform Mobile App (Expo / React Native).
* `apps/extension` — Cross-browser Extension (Manifest V3 for Chrome/Edge/Opera + Firefox/Safari WebExtension).

## Development Workflow

1. **Clone & Run Tests**:
   ```bash
   npm test
   ```
2. **Start the Web App & REST API Server**:
   ```bash
   npm start
   ```
   Open `http://localhost:3333` for the Web Reader UI or `http://localhost:3333/docs` for the OpenAPI documentation.
3. **Start the MCP Server**:
   ```bash
   npm run mcp
   ```

## Pull Request Guidelines

* Write unit or integration tests for new features or bug fixes.
* Follow conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
* Ensure `npm test` and `npm run lint` pass before submitting a PR.
