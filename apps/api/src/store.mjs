import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import {
  DEFAULT_READER_SETTINGS,
  chunkArticleIntoPassages,
  exportToCopyForLLM
} from "@summary-ai/shared";

/**
 * Persistent JSON/File Store for Summary AI:
 * Stores saved library items (articles, books, websites, YouTube transcripts),
 * reading history, multi-color annotations, chat threads, RSS feeds, reader settings,
 * and SHA-256 hashed API keys.
 */
export class SummaryStore {
  constructor({ dataFile = null } = {}) {
    this.dataFile = dataFile;
    this.state = {
      articles: {}, // id -> article object (with summaries, annotations, chatMessages, passages)
      history: [], // [{ id, articleId, title, url, sourceUsed, accessedAt }]
      feeds: {}, // id -> { id, title, feedUrl, items, createdAt, lastSyncedAt }
      apiKeys: {}, // id -> { id, name, keyPrefix, keyHash, scopes, createdAt, lastUsedAt, revokedAt }
      readerSettings: { ...DEFAULT_READER_SETTINGS },
      updatedAt: new Date().toISOString()
    };

    if (this.dataFile && fs.existsSync(this.dataFile)) {
      try {
        const raw = fs.readFileSync(this.dataFile, "utf8");
        const parsed = JSON.parse(raw);
        this.state = { ...this.state, ...parsed };
      } catch {
        // Start fresh if corrupted
      }
    }

    // Seed a built-in showcase article so first-time visitors can test every feature immediately
    if (Object.keys(this.state.articles).length === 0) {
      this.seedWelcomeArticle();
    }
  }

  persist() {
    this.state.updatedAt = new Date().toISOString();
    if (!this.dataFile) return;
    const dir = path.dirname(this.dataFile);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(this.dataFile, JSON.stringify(this.state, null, 2), "utf8");
  }

  seedWelcomeArticle() {
    const paragraphs = [
      "Summary AI is an open-source, agent-native reading, summarizing, and research platform inspired by smry.ai. Paste any article URL, book chapter, website, or YouTube video link to read in a calm, distraction-free environment with zero popups, cookie banners, or soft paywall overlays.",
      "When you submit a link, the Automatic Source Selection engine races Direct Fetch, the Internet Archive Wayback Machine, Google Cache mirrors, and reader proxies in parallel—scoring each response by completeness so you always get the full, unblocked text.",
      "Highlight any sentence in five semantic colors to attach personal margin notes, or click Contextual Ask AI to get instant explanations, definitions, or counterarguments scoped to that exact excerpt. When you are ready, export your structured highlights with one click to Obsidian, Notion, Roam Research, Markdown, or JSON.",
      "Turn any long-form essay into natural audio using the 10-voice Text-to-Speech engine with real-time Karaoke word-by-word highlighting. Click any word in the article to skip the audio narration directly to that timestamp, and adjust playback speed up to 2x.",
      "Every saved article, book, and RSS feed is automatically indexed with exact character offsets. Connect external AI agents via the Model Context Protocol (MCP) server or the OpenAPI REST interface using revocable API keys, ask a question weeks later, and receive the answer verified with the exact source passage."
    ];
    const textContent = paragraphs.join("\n\n");
    const contentHtml = paragraphs.map((p) => `<p>${p}</p>`).join("\n");
    const article = {
      id: "art_welcome_guide",
      url: "https://summary-ai.open/welcome-guide",
      title: "Welcome to Summary AI: Agentic Reading, Summarization & Verifiable Research",
      author: "Summary AI Open-Source Collective",
      siteName: "Summary AI Documentation",
      publishedTime: "2026-10-29",
      excerpt: paragraphs[0],
      contentHtml,
      textContent,
      markdown: paragraphs.join("\n\n"),
      wordCount: textContent.split(/\s+/).length,
      readingTimeMinutes: 2,
      mediaType: "article",
      sourceUsed: "direct",
      sourceAttempts: [
        { source: "direct", status: "ok", wordCount: 205, score: 132.5, latencyMs: 18, selected: true },
        { source: "wayback", status: "ok", wordCount: 205, score: 132.5, latencyMs: 94, selected: false }
      ],
      tags: ["welcome", "guide", "agentic-ai", "mcp"],
      savedInLibrary: true,
      savedAt: new Date().toISOString(),
      summaries: {},
      annotations: [
        {
          id: "ann_welcome_1",
          articleId: "art_welcome_guide",
          color: "yellow",
          quote: "Automatic Source Selection engine races Direct Fetch, the Internet Archive Wayback Machine, Google Cache mirrors, and reader proxies in parallel",
          note: "Multi-source racing ensures unblocked article recovery.",
          startOffset: paragraphs[0].length + 2,
          endOffset: paragraphs[0].length + 145,
          createdAt: new Date().toISOString()
        }
      ],
      chatMessages: []
    };
    article.passages = chunkArticleIntoPassages(article);
    article.llmMarkdown = exportToCopyForLLM(article);
    this.state.articles[article.id] = article;
  }

  saveArticle(article, { saveToLibrary = true, tags = [] } = {}) {
    const existing = this.state.articles[article.id] || {};
    const mergedTags = Array.from(new Set([...(existing.tags || []), ...(article.tags || []), ...tags]));
    const passages =
      Array.isArray(article.passages) && article.passages.length > 0
        ? article.passages
        : chunkArticleIntoPassages(article);

    const record = {
      ...existing,
      ...article,
      tags: mergedTags,
      passages,
      llmMarkdown: article.llmMarkdown || exportToCopyForLLM(article),
      savedInLibrary: saveToLibrary ? true : Boolean(existing.savedInLibrary),
      savedAt: existing.savedAt || new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      summaries: existing.summaries || article.summaries || {},
      annotations: existing.annotations || article.annotations || [],
      chatMessages: existing.chatMessages || article.chatMessages || []
    };

    this.state.articles[record.id] = record;
    this.recordHistory(record);
    this.persist();
    return record;
  }

  recordHistory(article) {
    const entry = {
      id: "hist_" + crypto.randomBytes(5).toString("hex"),
      articleId: article.id,
      title: article.title,
      url: article.url,
      sourceUsed: article.sourceUsed || "direct",
      wordCount: article.wordCount || 0,
      accessedAt: new Date().toISOString()
    };
    this.state.history = [
      entry,
      ...this.state.history.filter((h) => h.articleId !== article.id)
    ].slice(0, 200);
  }

  getArticle(id) {
    return this.state.articles[id] || null;
  }

  listLibrary({ query = "", tag = "" } = {}) {
    const q = String(query || "").trim().toLowerCase();
    const t = String(tag || "").trim().toLowerCase();
    return Object.values(this.state.articles)
      .filter((a) => a.savedInLibrary)
      .filter((a) => {
        if (t && !(a.tags || []).some((item) => item.toLowerCase() === t)) return false;
        if (!q) return true;
        return (
          String(a.title || "").toLowerCase().includes(q) ||
          String(a.textContent || "").toLowerCase().includes(q) ||
          String(a.url || "").toLowerCase().includes(q)
        );
      })
      .sort((a, b) => String(b.savedAt || "").localeCompare(String(a.savedAt || "")));
  }

  deleteArticle(id) {
    if (!this.state.articles[id]) return false;
    delete this.state.articles[id];
    this.persist();
    return true;
  }

  addAnnotation(articleId, { quote, note = "", color = "yellow", startOffset = null, endOffset = null }) {
    const art = this.getArticle(articleId);
    if (!art) throw new Error(`Article not found: ${articleId}`);
    const annotation = {
      id: "ann_" + crypto.randomBytes(6).toString("hex"),
      articleId,
      quote: String(quote || "").trim(),
      note: String(note || "").trim(),
      color: color || "yellow",
      startOffset,
      endOffset,
      createdAt: new Date().toISOString()
    };
    art.annotations = [...(art.annotations || []), annotation];
    this.persist();
    return annotation;
  }

  deleteAnnotation(articleId, annotationId) {
    const art = this.getArticle(articleId);
    if (!art) return false;
    const before = (art.annotations || []).length;
    art.annotations = (art.annotations || []).filter((a) => a.id !== annotationId);
    this.persist();
    return art.annotations.length < before;
  }

  saveSummary(articleId, summary) {
    const art = this.getArticle(articleId);
    if (!art) return summary;
    art.summaries = art.summaries || {};
    const key = `${summary.mode}_${summary.model}`;
    art.summaries[key] = summary;
    art.latestSummary = summary;
    this.persist();
    return summary;
  }

  appendChatMessages(articleId, messages = []) {
    const art = this.getArticle(articleId);
    if (!art) return;
    art.chatMessages = [...(art.chatMessages || []), ...messages];
    this.persist();
  }

  // API Keys Management (Create, List, Verify, Revoke)
  createApiKey({ name = "Agent Key", scopes = ["read", "write", "extract", "summarize", "mcp"] } = {}) {
    const rawSecret = "smry_live_" + crypto.randomBytes(18).toString("hex");
    const keyHash = crypto.createHash("sha256").update(rawSecret).digest("hex");
    const id = "key_" + crypto.randomBytes(6).toString("hex");
    const record = {
      id,
      name: String(name || "Agent Key").trim(),
      keyPrefix: rawSecret.slice(0, 16) + "...",
      keyHash,
      scopes,
      createdAt: new Date().toISOString(),
      lastUsedAt: null,
      revokedAt: null
    };
    this.state.apiKeys[id] = record;
    this.persist();
    return {
      ...record,
      apiKey: rawSecret // Returned only once upon creation
    };
  }

  listApiKeys() {
    return Object.values(this.state.apiKeys)
      .map(({ keyHash, ...safe }) => safe)
      .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
  }

  revokeApiKey(id) {
    const rec = this.state.apiKeys[id];
    if (!rec) return null;
    rec.revokedAt = new Date().toISOString();
    this.persist();
    const { keyHash, ...safe } = rec;
    return safe;
  }

  verifyApiKey(rawToken = "") {
    const cleaned = String(rawToken || "").trim();
    if (!cleaned) return { valid: false, reason: "missing_token" };
    const hash = crypto.createHash("sha256").update(cleaned).digest("hex");
    const found = Object.values(this.state.apiKeys).find((k) => k.keyHash === hash);
    if (!found) return { valid: false, reason: "invalid_key" };
    if (found.revokedAt) return { valid: false, reason: "revoked_key" };
    found.lastUsedAt = new Date().toISOString();
    this.persist();
    return { valid: true, keyRecord: found };
  }

  // RSS Feed Management
  saveFeed(feedData) {
    const id =
      feedData.id ||
      "feed_" + crypto.createHash("sha1").update(feedData.feedUrl || feedData.title).digest("hex").slice(0, 10);
    const record = {
      id,
      title: feedData.title || feedData.feedUrl,
      feedUrl: feedData.feedUrl,
      items: feedData.items || [],
      createdAt: this.state.feeds[id]?.createdAt || new Date().toISOString(),
      lastSyncedAt: new Date().toISOString()
    };
    this.state.feeds[id] = record;
    this.persist();
    return record;
  }

  listFeeds() {
    return Object.values(this.state.feeds);
  }

  deleteFeed(id) {
    if (!this.state.feeds[id]) return false;
    delete this.state.feeds[id];
    this.persist();
    return true;
  }

  // Cloud Sync Snapshot
  exportSyncSnapshot() {
    return {
      schemaVersion: "1.0",
      syncedAt: new Date().toISOString(),
      readerSettings: this.state.readerSettings,
      articles: Object.values(this.state.articles),
      history: this.state.history,
      feeds: Object.values(this.state.feeds)
    };
  }

  importSyncSnapshot(snapshot = {}) {
    if (snapshot.readerSettings) {
      this.state.readerSettings = { ...this.state.readerSettings, ...snapshot.readerSettings };
    }
    if (Array.isArray(snapshot.articles)) {
      for (const art of snapshot.articles) {
        if (art && art.id) {
          this.state.articles[art.id] = art;
        }
      }
    }
    if (Array.isArray(snapshot.feeds)) {
      for (const feed of snapshot.feeds) {
        if (feed && feed.id) {
          this.state.feeds[feed.id] = feed;
        }
      }
    }
    this.persist();
    return this.exportSyncSnapshot();
  }
}
