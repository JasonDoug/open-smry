import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  READER_FONTS,
  DEFAULT_READER_SETTINGS,
  HIGHLIGHT_COLORS,
  EXTRACTION_SOURCES,
  AI_MODELS,
  SUMMARY_MODES,
  TTS_VOICES,
  filterAnnotations,
  exportKnowledge,
  exportToCopyForLLM
} from "@summary-ai/shared";
import {
  extractFromUrl,
  sanitizeAndExtractHtml,
  parseRssOrAtomFeed
} from "@summary-ai/extractor";
import {
  generateSummary,
  contextualAskAi,
  askLibraryWithCitations,
  streamChatResponse,
  buildKaraokeWordTimeline,
  findWordAtTimestamp
} from "@summary-ai/ai";
import { SummaryStore } from "./store.mjs";
import { buildOpenApiSpec } from "./openapi.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEB_PUBLIC_DIR = path.resolve(__dirname, "../../web/public");

function sendJson(res, statusCode, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key"
  });
  res.end(body);
}

async function readJsonBody(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf8").trim();
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    throw new Error("Invalid JSON request body");
  }
}

function extractApiKeyFromHeaders(req) {
  const xKey = req.headers["x-api-key"];
  if (typeof xKey === "string" && xKey.trim()) return xKey.trim();
  const auth = req.headers.authorization;
  if (typeof auth === "string" && /^Bearer\s+/i.test(auth)) {
    return auth.replace(/^Bearer\s+/i, "").trim();
  }
  return null;
}

export function createApiServer({
  store = new SummaryStore(),
  fetchImpl = globalThis.fetch,
  env = process.env
} = {}) {
  const server = http.createServer(async (req, res) => {
    try {
      if (req.method === "OPTIONS") {
        res.writeHead(204, {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key"
        });
        res.end();
        return;
      }

      const host = req.headers.host || "localhost:3333";
      const parsedUrl = new URL(req.url || "/", `http://${host}`);
      const pathname = parsedUrl.pathname;

      // Optional API Key verification: if a client/agent provides an API key, verify it strictly.
      // If no API key is provided, allow "No Account Required" instant access.
      const providedKey = extractApiKeyFromHeaders(req);
      if (providedKey) {
        const verification = store.verifyApiKey(providedKey);
        if (!verification.valid) {
          sendJson(res, 401, {
            error: "Unauthorized API Key",
            reason: verification.reason
          });
          return;
        }
      }

      // OpenAPI 3.1 Spec
      if (req.method === "GET" && pathname === "/openapi.json") {
        sendJson(res, 200, buildOpenApiSpec(`http://${host}`));
        return;
      }

      // Interactive OpenAPI Docs Page
      if (req.method === "GET" && pathname === "/docs") {
        const spec = buildOpenApiSpec(`http://${host}`);
        const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Summary AI — OpenAPI 3.1 & Agent Documentation</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #0b0f19; color: #e2e8f0; margin: 0; padding: 2rem; line-height: 1.6; }
    .container { max-width: 960px; margin: 0 auto; }
    h1, h2 { color: #f8fafc; }
    .endpoint { background: #111827; border: 1px solid #1e293b; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
    .method { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: 700; font-size: 0.8rem; margin-right: 0.5rem; background: #3b82f6; color: white; }
    pre { background: #090d16; padding: 1rem; border-radius: 6px; overflow-x: auto; border: 1px solid #1e293b; }
    a { color: #38bdf8; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Summary AI — HTTP REST & OpenAPI 3.1 Reference</h1>
    <p><a href="/">← Back to Summary AI Reader</a> | <a href="/openapi.json">Raw OpenAPI 3.1 JSON (/openapi.json)</a></p>
    ${Object.entries(spec.paths)
      .map(([route, methods]) =>
        Object.entries(methods)
          .map(
            ([m, info]) =>
              `<div class="endpoint"><span class="method">${m.toUpperCase()}</span><code>${route}</code><p>${info.summary || ""}</p></div>`
          )
          .join("")
      )
      .join("")}
  </div>
</body>
</html>`;
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(html);
        return;
      }

      // System Metadata & Reader Constants
      if (req.method === "GET" && pathname === "/api/v1/meta") {
        sendJson(res, 200, {
          name: "Summary AI",
          version: "1.0.0",
          noAccountRequired: true,
          readerFonts: READER_FONTS,
          defaultReaderSettings: store.state.readerSettings || DEFAULT_READER_SETTINGS,
          highlightColors: HIGHLIGHT_COLORS,
          extractionSources: EXTRACTION_SOURCES,
          aiModels: AI_MODELS,
          summaryModes: SUMMARY_MODES,
          ttsVoices: TTS_VOICES
        });
        return;
      }

      // Extract URL / YouTube / Raw HTML
      if (req.method === "POST" && pathname === "/api/v1/extract") {
        const body = await readJsonBody(req);
        const {
          url,
          source = "auto",
          rawHtml = null,
          textContent = null,
          title = null,
          saveToLibrary = true,
          tags = []
        } = body;

        let extracted;
        if (textContent && !rawHtml && !url) {
          const syntheticHtml = `<article><h1>${title || "Submitted Document"}</h1>${String(textContent)
            .split(/\n\s*\n/)
            .map((p) => `<p>${p.trim()}</p>`)
            .join("")}</article>`;
          extracted = sanitizeAndExtractHtml(syntheticHtml, "local://document");
          extracted.sourceUsed = "direct-text";
          extracted.sourceAttempts = [{ source: "direct-text", status: "ok", wordCount: extracted.wordCount, score: 100, latencyMs: 1, selected: true }];
        } else {
          extracted = await extractFromUrl(url || "local://html", {
            preferredSource: source,
            fetchImpl,
            rawHtmlOverride: rawHtml
          });
          if (title) extracted.title = title;
        }

        const saved = store.saveArticle(extracted, { saveToLibrary, tags });
        sendJson(res, 200, { article: saved });
        return;
      }

      // One-Shot Ingest: Read, Summarize, Index Passages, and File into Library
      if (req.method === "POST" && pathname === "/api/v1/ingest") {
        const body = await readJsonBody(req);
        const {
          url,
          rawHtml = null,
          textContent = null,
          title = null,
          source = "auto",
          tags = [],
          model = "claude-3-7-sonnet",
          summaryMode = "bullets"
        } = body;

        let extracted;
        if (textContent && !rawHtml) {
          const syntheticHtml = `<article><h1>${title || "Saved Book / Article"}</h1>${String(textContent)
            .split(/\n\s*\n/)
            .map((p) => `<p>${p.trim()}</p>`)
            .join("")}</article>`;
          extracted = sanitizeAndExtractHtml(syntheticHtml, url || "library://item");
          extracted.sourceUsed = "direct-ingest";
        } else {
          extracted = await extractFromUrl(url, {
            preferredSource: source,
            fetchImpl,
            rawHtmlOverride: rawHtml
          });
          if (title) extracted.title = title;
        }

        const saved = store.saveArticle(extracted, { saveToLibrary: true, tags });
        const summary = await generateSummary(saved, { mode: summaryMode, model, env, fetchImpl });
        store.saveSummary(saved.id, summary);

        sendJson(res, 201, {
          article: store.getArticle(saved.id),
          summary
        });
        return;
      }

      // Summarize Article
      if (req.method === "POST" && pathname === "/api/v1/summarize") {
        const body = await readJsonBody(req);
        const {
          articleId,
          article: inlineArticle,
          mode = "bullets",
          model = "claude-3-7-sonnet",
          customPrompt = ""
        } = body;

        const targetArticle = (articleId && store.getArticle(articleId)) || inlineArticle;
        if (!targetArticle) {
          sendJson(res, 404, { error: "Article not found for summarization." });
          return;
        }

        const summary = await generateSummary(targetArticle, {
          mode,
          model,
          customPrompt,
          env,
          fetchImpl
        });

        if (targetArticle.id && store.getArticle(targetArticle.id)) {
          store.saveSummary(targetArticle.id, summary);
        }

        sendJson(res, 200, { summary });
        return;
      }

      // Contextual "Ask AI" on Highlighted Excerpt
      if (req.method === "POST" && pathname === "/api/v1/ask-context") {
        const body = await readJsonBody(req);
        const {
          articleId,
          article: inlineArticle,
          selectionText,
          action = "explain",
          question = "",
          model = "claude-3-7-sonnet"
        } = body;

        const targetArticle = (articleId && store.getArticle(articleId)) || inlineArticle;
        const result = await contextualAskAi({
          article: targetArticle,
          selectionText,
          action,
          question,
          model,
          env,
          fetchImpl
        });

        sendJson(res, 200, result);
        return;
      }

      // Interactive AI Chat (Supports SSE word-by-word streaming and JSON)
      if (req.method === "POST" && pathname === "/api/v1/chat") {
        const body = await readJsonBody(req);
        const {
          articleId,
          article: inlineArticle,
          messages = [],
          question = "",
          model = "claude-3-7-sonnet",
          stream = false
        } = body;

        const targetArticle = (articleId && store.getArticle(articleId)) || inlineArticle;
        const chatMessages =
          messages.length > 0
            ? messages
            : [{ role: "user", content: question || "What are the key insights of this article?" }];

        if (stream) {
          res.writeHead(200, {
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache, no-transform",
            Connection: "keep-alive",
            "Access-Control-Allow-Origin": "*"
          });

          for await (const event of streamChatResponse({
            article: targetArticle,
            messages: chatMessages,
            model,
            env,
            fetchImpl
          })) {
            res.write(`data: ${JSON.stringify(event)}\n\n`);
            if (event.type === "done" && targetArticle?.id) {
              store.appendChatMessages(targetArticle.id, [
                chatMessages[chatMessages.length - 1],
                {
                  role: "assistant",
                  content: event.fullText,
                  model: event.model,
                  citations: event.citations,
                  createdAt: new Date().toISOString()
                }
              ]);
            }
          }
          res.end();
          return;
        }

        let finalEvent = null;
        for await (const event of streamChatResponse({
          article: targetArticle,
          messages: chatMessages,
          model,
          env,
          fetchImpl
        })) {
          if (event.type === "done") finalEvent = event;
        }

        if (targetArticle?.id && finalEvent) {
          store.appendChatMessages(targetArticle.id, [
            chatMessages[chatMessages.length - 1],
            {
              role: "assistant",
              content: finalEvent.fullText,
              model: finalEvent.model,
              citations: finalEvent.citations,
              createdAt: new Date().toISOString()
            }
          ]);
        }

        sendJson(res, 200, {
          reply: finalEvent?.fullText || "",
          model: finalEvent?.model || model,
          modelName: finalEvent?.modelName || model,
          citations: finalEvent?.citations || []
        });
        return;
      }

      // Library List
      if (req.method === "GET" && pathname === "/api/v1/library") {
        const query = parsedUrl.searchParams.get("q") || "";
        const tag = parsedUrl.searchParams.get("tag") || "";
        const items = store.listLibrary({ query, tag });
        sendJson(res, 200, { articles: items, total: items.length });
        return;
      }

      // Ask Library Question -> Returns Answer + Exact Cited Passage & Character Offsets
      if (req.method === "POST" && pathname === "/api/v1/library/ask") {
        const body = await readJsonBody(req);
        const { question, articleIds = null, model = "claude-3-7-sonnet", topK = 4 } = body;
        const allLibrary = store.listLibrary();
        const scopedArticles = Array.isArray(articleIds) && articleIds.length > 0
          ? allLibrary.filter((a) => articleIds.includes(a.id))
          : allLibrary;

        const ragResponse = await askLibraryWithCitations({
          articles: scopedArticles,
          question,
          model,
          topK,
          env,
          fetchImpl
        });

        sendJson(res, 200, ragResponse);
        return;
      }

      // Single Library Item GET / DELETE
      const libraryItemMatch = pathname.match(/^\/api\/v1\/library\/([^/]+)$/);
      if (libraryItemMatch) {
        const id = decodeURIComponent(libraryItemMatch[1]);
        if (req.method === "GET") {
          const item = store.getArticle(id);
          if (!item) {
            sendJson(res, 404, { error: "Library article not found" });
            return;
          }
          sendJson(res, 200, { article: item });
          return;
        }
        if (req.method === "DELETE") {
          const deleted = store.deleteArticle(id);
          sendJson(res, deleted ? 200 : 404, { deleted, id });
          return;
        }
      }

      // Reading History
      if (req.method === "GET" && pathname === "/api/v1/history") {
        sendJson(res, 200, { history: store.state.history });
        return;
      }

      // Annotations GET / POST
      const annRouteMatch = pathname.match(/^\/api\/v1\/articles\/([^/]+)\/annotations$/);
      if (annRouteMatch) {
        const articleId = decodeURIComponent(annRouteMatch[1]);
        const article = store.getArticle(articleId);
        if (!article) {
          sendJson(res, 404, { error: "Article not found" });
          return;
        }

        if (req.method === "GET") {
          const color = parsedUrl.searchParams.get("color") || "all";
          const query = parsedUrl.searchParams.get("q") || "";
          const annotations = filterAnnotations(article.annotations || [], { color, query });
          sendJson(res, 200, { annotations });
          return;
        }

        if (req.method === "POST") {
          const body = await readJsonBody(req);
          const created = store.addAnnotation(articleId, body);
          sendJson(res, 201, { annotation: created, annotations: article.annotations });
          return;
        }
      }

      // Annotation DELETE
      const annDeleteMatch = pathname.match(/^\/api\/v1\/articles\/([^/]+)\/annotations\/([^/]+)$/);
      if (annDeleteMatch && req.method === "DELETE") {
        const articleId = decodeURIComponent(annDeleteMatch[1]);
        const annotationId = decodeURIComponent(annDeleteMatch[2]);
        const deleted = store.deleteAnnotation(articleId, annotationId);
        sendJson(res, deleted ? 200 : 404, { deleted, annotationId });
        return;
      }

      // PKM & LLM Exports (Notion, Obsidian, Roam, Markdown, JSON, Copy-to-LLM)
      const exportMatch = pathname.match(/^\/api\/v1\/articles\/([^/]+)\/export$/);
      if (exportMatch && req.method === "GET") {
        const articleId = decodeURIComponent(exportMatch[1]);
        const format = (parsedUrl.searchParams.get("format") || "markdown").toLowerCase();
        const article = store.getArticle(articleId);
        if (!article) {
          sendJson(res, 404, { error: "Article not found" });
          return;
        }

        const content =
          format === "llm"
            ? exportToCopyForLLM(article)
            : exportKnowledge(article, article.annotations || [], article.latestSummary || null, format);

        sendJson(res, 200, {
          articleId,
          format,
          content
        });
        return;
      }

      // TTS & Karaoke Word-by-Word Timestamp Timeline
      if (req.method === "POST" && pathname === "/api/v1/tts/timeline") {
        const body = await readJsonBody(req);
        const {
          articleId,
          textContent = "",
          voiceId = "aria-us-f",
          speed = 1.0,
          timestampMs = null
        } = body;

        const article = articleId ? store.getArticle(articleId) : null;
        const text = textContent || article?.textContent || "";
        const timeline = buildKaraokeWordTimeline(text, { voiceId, speed });
        const activeWord =
          timestampMs !== null ? findWordAtTimestamp(timeline, timestampMs) : null;

        sendJson(res, 200, {
          timeline,
          activeWord
        });
        return;
      }

      // RSS Feeds GET / POST / DELETE
      if (pathname === "/api/v1/feeds") {
        if (req.method === "GET") {
          sendJson(res, 200, { feeds: store.listFeeds() });
          return;
        }
        if (req.method === "POST") {
          const body = await readJsonBody(req);
          const { feedUrl, rawXml = null, autoIngestTop = 0 } = body;
          let xml = rawXml;
          if (!xml && feedUrl && typeof fetchImpl === "function") {
            const feedRes = await fetchImpl(feedUrl);
            if (feedRes.ok) {
              xml = await feedRes.text();
            }
          }
          const parsedFeed = parseRssOrAtomFeed(xml || "", feedUrl);
          const savedFeed = store.saveFeed(parsedFeed);

          const ingestedArticles = [];
          const count = Math.min(Number(autoIngestTop) || 0, savedFeed.items.length, 5);
          for (let i = 0; i < count; i += 1) {
            const item = savedFeed.items[i];
            const syntheticHtml = `<article><h1>${item.title}</h1><p>${item.summary || item.title}</p></article>`;
            const art = sanitizeAndExtractHtml(syntheticHtml, item.url || savedFeed.feedUrl);
            art.sourceUsed = "rss-feed";
            ingestedArticles.push(store.saveArticle(art, { saveToLibrary: true, tags: ["rss"] }));
          }

          sendJson(res, 201, {
            feed: savedFeed,
            ingestedArticles
          });
          return;
        }
      }

      const feedDeleteMatch = pathname.match(/^\/api\/v1\/feeds\/([^/]+)$/);
      if (feedDeleteMatch && req.method === "DELETE") {
        const feedId = decodeURIComponent(feedDeleteMatch[1]);
        const deleted = store.deleteFeed(feedId);
        sendJson(res, deleted ? 200 : 404, { deleted, feedId });
        return;
      }

      // API Keys GET / POST / DELETE
      if (pathname === "/api/v1/keys") {
        if (req.method === "GET") {
          sendJson(res, 200, { keys: store.listApiKeys() });
          return;
        }
        if (req.method === "POST") {
          const body = await readJsonBody(req);
          const created = store.createApiKey({
            name: body.name || "Agent API Key",
            scopes: body.scopes
          });
          sendJson(res, 201, { key: created });
          return;
        }
      }

      const keyDeleteMatch = pathname.match(/^\/api\/v1\/keys\/([^/]+)$/);
      if (keyDeleteMatch && req.method === "DELETE") {
        const keyId = decodeURIComponent(keyDeleteMatch[1]);
        const revoked = store.revokeApiKey(keyId);
        if (!revoked) {
          sendJson(res, 404, { error: "API Key not found" });
          return;
        }
        sendJson(res, 200, { key: revoked });
        return;
      }

      // Cloud Sync GET / POST
      if (pathname === "/api/v1/sync") {
        if (req.method === "GET") {
          sendJson(res, 200, store.exportSyncSnapshot());
          return;
        }
        if (req.method === "POST") {
          const body = await readJsonBody(req);
          const updated = store.importSyncSnapshot(body);
          sendJson(res, 200, updated);
          return;
        }
      }

      // Serve Web Reader Static Files (apps/web/public)
      if (req.method === "GET") {
        const cleanPath = pathname === "/" ? "/index.html" : pathname;
        const candidatePath = path.resolve(WEB_PUBLIC_DIR, "." + cleanPath);
        if (candidatePath.startsWith(WEB_PUBLIC_DIR) && fs.existsSync(candidatePath) && fs.statSync(candidatePath).isFile()) {
          const ext = path.extname(candidatePath).toLowerCase();
          const mimeMap = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".mjs": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml"
          };
          res.writeHead(200, {
            "Content-Type": mimeMap[ext] || "text/plain; charset=utf-8"
          });
          res.end(fs.readFileSync(candidatePath));
          return;
        }
      }

      sendJson(res, 404, { error: `Route not found: ${req.method} ${pathname}` });
    } catch (err) {
      sendJson(res, 500, {
        error: err?.message || "Internal server error"
      });
    }
  });

  return { server, store };
}
