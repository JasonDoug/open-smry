export function buildOpenApiSpec(baseUrl = "http://localhost:3333") {
  return {
    openapi: "3.1.0",
    info: {
      title: "Summary AI — Open-Source Agentic Reading, Summarizing & Research API",
      version: "1.0.0",
      description:
        "REST HTTP API for multi-source distraction-free article extraction, YouTube transcripts, customizable multi-LLM summarization (Claude, GPT, Gemini), streaming AI chat, contextual Ask AI, multi-color annotations, PKM exports (Notion, Obsidian, Roam, Markdown, JSON), Karaoke TTS timelines, RSS feeds, API key management, and exact-passage RAG retrieval.",
      license: {
        name: "MIT",
        url: "https://opensource.org/licenses/MIT"
      }
    },
    servers: [{ url: baseUrl, description: "Summary AI Server" }],
    components: {
      securitySchemes: {
        BearerApiKey: {
          type: "http",
          scheme: "bearer",
          bearerFormat: "smry_live_<token>",
          description: "API Key created via POST /api/v1/keys (or passed via X-API-Key header)."
        }
      }
    },
    paths: {
      "/api/v1/meta": {
        get: {
          summary: "Get reader fonts, AI models, summary modes, highlight colors, and 10 TTS voices",
          tags: ["System"]
        }
      },
      "/api/v1/extract": {
        post: {
          summary: "Extract distraction-free article or YouTube transcript by racing mirrors (No Account Required)",
          tags: ["Extraction & Reader"],
          requestBody: {
            required: true,
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  properties: {
                    url: { type: "string", examples: ["https://example.com/article"] },
                    source: { type: "string", enum: ["auto", "direct", "wayback", "googlecache", "jina"] },
                    rawHtml: { type: "string" },
                    saveToLibrary: { type: "boolean", default: true }
                  }
                }
              }
            }
          }
        }
      },
      "/api/v1/ingest": {
        post: {
          summary: "Save an article, book, or website: automatically read, summarized, indexed, and filed",
          tags: ["Library & RAG"]
        }
      },
      "/api/v1/summarize": {
        post: {
          summary: "Generate customizable AI summary (tldr, bullets, takeaways, executive, custom prompt)",
          tags: ["AI Summarization & Chat"]
        }
      },
      "/api/v1/chat": {
        post: {
          summary: "Interactive AI chat with real-time SSE word-by-word streaming and exact passage citations",
          tags: ["AI Summarization & Chat"]
        }
      },
      "/api/v1/ask-context": {
        post: {
          summary: "Contextual Ask AI on a highlighted passage (explain, define, summarize, critique, custom)",
          tags: ["AI Summarization & Chat"]
        }
      },
      "/api/v1/library": {
        get: {
          summary: "List saved articles, books, and websites in library",
          tags: ["Library & RAG"]
        }
      },
      "/api/v1/library/ask": {
        post: {
          summary: "Ask a question across saved library items and get the answer with the exact passage and character offsets",
          tags: ["Library & RAG"]
        }
      },
      "/api/v1/history": {
        get: {
          summary: "Get reading and extraction history",
          tags: ["Library & RAG"]
        }
      },
      "/api/v1/articles/{id}/annotations": {
        get: {
          summary: "List and filter multi-color highlights and margin notes",
          tags: ["Annotations & PKM Export"]
        },
        post: {
          summary: "Create a multi-color highlight and margin note",
          tags: ["Annotations & PKM Export"]
        }
      },
      "/api/v1/articles/{id}/export": {
        get: {
          summary: "Export article, summary, and highlights to Notion, Obsidian, Roam Research, Markdown, JSON, or Copy-to-LLM",
          tags: ["Annotations & PKM Export"]
        }
      },
      "/api/v1/tts/timeline": {
        post: {
          summary: "Generate 10-voice Natural TTS & Karaoke word-by-word timestamp map",
          tags: ["TTS & Audio"]
        }
      },
      "/api/v1/feeds": {
        get: { summary: "List subscribed RSS/Atom feeds", tags: ["RSS & Agents"] },
        post: { summary: "Subscribe and ingest RSS/Atom feed", tags: ["RSS & Agents"] }
      },
      "/api/v1/keys": {
        get: { summary: "List API keys for agents, scripts, curl, and CI", tags: ["Agent API Keys"] },
        post: { summary: "Create a new API key (smry_live_...)", tags: ["Agent API Keys"] }
      },
      "/api/v1/keys/{id}": {
        delete: { summary: "Revoke an API key", tags: ["Agent API Keys"] }
      },
      "/api/v1/sync": {
        get: { summary: "Export cross-device cloud sync state", tags: ["Cloud Sync"] },
        post: { summary: "Import cross-device cloud sync state", tags: ["Cloud Sync"] }
      }
    }
  };
}
