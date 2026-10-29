#!/usr/bin/env node
import readline from "node:readline";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { exportKnowledge, exportToCopyForLLM } from "@summary-ai/shared";
import { extractFromUrl, sanitizeAndExtractHtml, parseRssOrAtomFeed } from "@summary-ai/extractor";
import { generateSummary, askLibraryWithCitations } from "@summary-ai/ai";
import { SummaryStore } from "@summary-ai/api/store";

export const MCP_TOOLS = [
  {
    name: "extract_article",
    description:
      "Extracts clean, distraction-free text, Markdown, or YouTube transcript from any URL by racing Direct, Wayback Machine, and Archive mirrors.",
    inputSchema: {
      type: "object",
      properties: {
        url: { type: "string", description: "Target article or YouTube URL" },
        source: {
          type: "string",
          enum: ["auto", "direct", "wayback", "googlecache", "jina"],
          default: "auto"
        }
      },
      required: ["url"]
    }
  },
  {
    name: "save_and_summarize",
    description:
      "Saves an article, book chapter, or website to the user's Library, automatically reads it, generates a customizable AI summary, and indexes passages with exact character offsets.",
    inputSchema: {
      type: "object",
      properties: {
        url: { type: "string", description: "Article or website URL" },
        title: { type: "string", description: "Optional title override" },
        textContent: { type: "string", description: "Optional direct text or book chapter content" },
        model: {
          type: "string",
          enum: ["claude-3-7-sonnet", "gpt-4o", "gemini-2.5-pro"],
          default: "claude-3-7-sonnet"
        },
        summaryMode: {
          type: "string",
          enum: ["tldr", "bullets", "takeaways", "executive", "custom"],
          default: "bullets"
        },
        tags: { type: "array", items: { type: "string" } }
      }
    }
  },
  {
    name: "ask_library",
    description:
      "Asks a question across saved articles, books, and websites in the Library and returns the synthesized answer with exact source passages and character offsets.",
    inputSchema: {
      type: "object",
      properties: {
        question: { type: "string", description: "Question to answer from saved library items" },
        model: {
          type: "string",
          enum: ["claude-3-7-sonnet", "gpt-4o", "gemini-2.5-pro"],
          default: "claude-3-7-sonnet"
        },
        topK: { type: "number", default: 3 }
      },
      required: ["question"]
    }
  },
  {
    name: "list_saved_articles",
    description: "Lists saved articles, books, and websites in the Library with optional keyword or tag filtering.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string" },
        tag: { type: "string" }
      }
    }
  },
  {
    name: "get_reading_history",
    description: "Returns the chronological reading and extraction history.",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "number", default: 25 }
      }
    }
  },
  {
    name: "export_article_knowledge",
    description:
      "Exports a saved article's highlights, margin notes, and summary to Notion, Obsidian, Roam Research, Markdown, JSON, or LLM-ready Markdown.",
    inputSchema: {
      type: "object",
      properties: {
        articleId: { type: "string" },
        format: {
          type: "string",
          enum: ["markdown", "obsidian", "notion", "roam", "json", "llm"],
          default: "markdown"
        }
      },
      required: ["articleId"]
    }
  },
  {
    name: "manage_rss_feeds",
    description: "Lists subscribed RSS/Atom feeds or subscribes to a new RSS feed URL for automated agent ingestion.",
    inputSchema: {
      type: "object",
      properties: {
        action: { type: "string", enum: ["list", "subscribe"], default: "list" },
        feedUrl: { type: "string" },
        rawXml: { type: "string" }
      }
    }
  }
];

export class SummaryMcpServer {
  constructor({ store = new SummaryStore(), fetchImpl = globalThis.fetch } = {}) {
    this.store = store;
    this.fetchImpl = fetchImpl;
  }

  async handleJsonRpc(request) {
    const { id = null, method, params = {} } = request || {};

    try {
      if (method === "initialize") {
        return {
          jsonrpc: "2.0",
          id,
          result: {
            protocolVersion: "2024-11-05",
            serverInfo: {
              name: "summary-ai-mcp",
              version: "1.0.0"
            },
            capabilities: {
              tools: {},
              resources: {}
            }
          }
        };
      }

      if (method === "tools/list") {
        return {
          jsonrpc: "2.0",
          id,
          result: {
            tools: MCP_TOOLS
          }
        };
      }

      if (method === "resources/list") {
        const articles = this.store.listLibrary();
        return {
          jsonrpc: "2.0",
          id,
          result: {
            resources: [
              {
                uri: "library://history",
                name: "Reading History",
                mimeType: "application/json"
              },
              ...articles.map((a) => ({
                uri: `library://articles/${a.id}`,
                name: a.title,
                mimeType: "text/markdown"
              }))
            ]
          }
        };
      }

      if (method === "resources/read") {
        const uri = params.uri || "";
        if (uri === "library://history") {
          return {
            jsonrpc: "2.0",
            id,
            result: {
              contents: [
                {
                  uri,
                  mimeType: "application/json",
                  text: JSON.stringify(this.store.state.history, null, 2)
                }
              ]
            }
          };
        }
        const artMatch = uri.match(/^library:\/\/articles\/(.+)$/);
        if (artMatch) {
          const art = this.store.getArticle(artMatch[1]);
          if (!art) throw new Error(`Article resource not found: ${uri}`);
          return {
            jsonrpc: "2.0",
            id,
            result: {
              contents: [
                {
                  uri,
                  mimeType: "text/markdown",
                  text: exportToCopyForLLM(art)
                }
              ]
            }
          };
        }
        throw new Error(`Unsupported resource URI: ${uri}`);
      }

      if (method === "tools/call") {
        const toolName = params.name;
        const args = params.arguments || {};
        const output = await this.executeTool(toolName, args);
        return {
          jsonrpc: "2.0",
          id,
          result: {
            content: [
              {
                type: "text",
                text: typeof output === "string" ? output : JSON.stringify(output, null, 2)
              }
            ]
          }
        };
      }

      return {
        jsonrpc: "2.0",
        id,
        error: {
          code: -32601,
          message: `Method not found: ${method}`
        }
      };
    } catch (err) {
      return {
        jsonrpc: "2.0",
        id,
        error: {
          code: -32000,
          message: err?.message || "MCP execution error"
        }
      };
    }
  }

  async executeTool(name, args = {}) {
    switch (name) {
      case "extract_article": {
        const article = await extractFromUrl(args.url, {
          preferredSource: args.source || "auto",
          fetchImpl: this.fetchImpl
        });
        this.store.saveArticle(article, { saveToLibrary: false });
        return {
          id: article.id,
          title: article.title,
          url: article.url,
          sourceUsed: article.sourceUsed,
          wordCount: article.wordCount,
          llmMarkdown: article.llmMarkdown
        };
      }

      case "save_and_summarize": {
        let extracted;
        if (args.textContent) {
          const html = `<article><h1>${args.title || "Saved Document"}</h1>${String(args.textContent)
            .split(/\n\s*\n/)
            .map((p) => `<p>${p.trim()}</p>`)
            .join("")}</article>`;
          extracted = sanitizeAndExtractHtml(html, args.url || "library://document");
          extracted.sourceUsed = "mcp-agent";
        } else {
          extracted = await extractFromUrl(args.url, { fetchImpl: this.fetchImpl });
          if (args.title) extracted.title = args.title;
        }
        const saved = this.store.saveArticle(extracted, {
          saveToLibrary: true,
          tags: args.tags || ["mcp-saved"]
        });
        const summary = await generateSummary(saved, {
          mode: args.summaryMode || "bullets",
          model: args.model || "claude-3-7-sonnet",
          fetchImpl: this.fetchImpl
        });
        this.store.saveSummary(saved.id, summary);
        return {
          articleId: saved.id,
          title: saved.title,
          url: saved.url,
          summary: summary.content,
          passageCount: saved.passages.length
        };
      }

      case "ask_library": {
        const articles = this.store.listLibrary();
        return await askLibraryWithCitations({
          articles,
          question: args.question,
          model: args.model || "claude-3-7-sonnet",
          topK: args.topK || 3,
          fetchImpl: this.fetchImpl
        });
      }

      case "list_saved_articles": {
        const items = this.store.listLibrary({ query: args.query, tag: args.tag });
        return items.map((a) => ({
          id: a.id,
          title: a.title,
          url: a.url,
          wordCount: a.wordCount,
          tags: a.tags,
          savedAt: a.savedAt
        }));
      }

      case "get_reading_history": {
        return this.store.state.history.slice(0, Number(args.limit) || 25);
      }

      case "export_article_knowledge": {
        const art = this.store.getArticle(args.articleId);
        if (!art) throw new Error(`Article not found: ${args.articleId}`);
        if (args.format === "llm") return exportToCopyForLLM(art);
        return exportKnowledge(art, art.annotations || [], art.latestSummary || null, args.format || "markdown");
      }

      case "manage_rss_feeds": {
        if (args.action === "subscribe") {
          let xml = args.rawXml || "";
          if (!xml && args.feedUrl && typeof this.fetchImpl === "function") {
            const r = await this.fetchImpl(args.feedUrl);
            if (r.ok) xml = await r.text();
          }
          const parsed = parseRssOrAtomFeed(xml, args.feedUrl);
          return this.store.saveFeed(parsed);
        }
        return this.store.listFeeds();
      }

      default:
        throw new Error(`Unknown MCP tool: ${name}`);
    }
  }
}

// Run over stdio if invoked directly as CLI binary
const isMain =
  process.argv[1] &&
  path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url));

if (isMain) {
  const dataDir = process.env.DATA_DIR || path.resolve(process.cwd(), ".data");
  const store = new SummaryStore({
    dataFile: path.join(dataDir, "summary-ai-store.json")
  });
  const mcpServer = new SummaryMcpServer({ store });
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
  });

  rl.on("line", async (line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    try {
      const req = JSON.parse(trimmed);
      const res = await mcpServer.handleJsonRpc(req);
      process.stdout.write(JSON.stringify(res) + "\n");
    } catch (err) {
      process.stdout.write(
        JSON.stringify({
          jsonrpc: "2.0",
          id: null,
          error: { code: -32700, message: err?.message || "Parse error" }
        }) + "\n"
      );
    }
  });
}
