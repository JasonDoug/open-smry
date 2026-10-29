import test from "node:test";
import assert from "node:assert/strict";
import {
  READER_FONTS,
  HIGHLIGHT_COLORS,
  TTS_VOICES,
  exportToCopyForLLM,
  filterAnnotations,
  exportKnowledge,
  chunkArticleIntoPassages,
  findExactPassages
} from "../src/index.mjs";

test("Sprint 1: READER_FONTS includes 7 fonts including OpenDyslexic", () => {
  assert.equal(READER_FONTS.length, 7);
  const dyslexic = READER_FONTS.find((f) => f.id === "opendyslexic");
  assert.ok(dyslexic, "OpenDyslexic font should be registered");
  assert.equal(HIGHLIGHT_COLORS.length, 5);
  assert.equal(TTS_VOICES.length, 10);
});

test("Sprint 1: exportToCopyForLLM produces clean LLM-ready Markdown", () => {
  const md = exportToCopyForLLM({
    title: "Understanding Agentic Retrieval",
    url: "https://example.com/agentic-rag",
    author: "Dr. Ada Lovelace",
    siteName: "AI Research Weekly",
    sourceUsed: "wayback",
    readingTimeMinutes: 4,
    wordCount: 812,
    markdown: "## Core Thesis\n\nAgents require deterministic passage offsets."
  });
  assert.match(md, /# Understanding Agentic Retrieval/);
  assert.match(md, /Source URL:\*\* https:\/\/example\.com\/agentic-rag/);
  assert.match(md, /Agents require deterministic passage offsets\./);
});

test("Sprint 1: filterAnnotations filters by color and search query", () => {
  const annotations = [
    { id: "1", color: "yellow", quote: "Soft paywalls block casual readers", note: "Key problem" },
    { id: "2", color: "green", quote: "Wayback Machine stores historical snapshots", note: "Archive fallback" },
    { id: "3", color: "yellow", quote: "OpenDyslexic improves reading comfort", note: "Typography" }
  ];

  assert.equal(filterAnnotations(annotations, { color: "yellow" }).length, 2);
  assert.equal(filterAnnotations(annotations, { color: "green" }).length, 1);
  assert.equal(filterAnnotations(annotations, { color: "all", query: "archive" }).length, 1);
  assert.equal(filterAnnotations(annotations, { color: "yellow", query: "dyslexic" }).length, 1);
});

test("Sprint 1: exportKnowledge supports Notion, Obsidian, Roam, Markdown, and JSON", () => {
  const article = {
    id: "art_1",
    title: "The Future of Open Protocols",
    url: "https://example.org/protocols",
    author: "Tim Berners",
    tags: ["mcp", "web"]
  };
  const annotations = [
    { id: "h1", color: "blue", quote: "MCP standardizes tool invocation for agents.", note: "Crucial for interoperability" }
  ];
  const summary = { content: "- Standardizes agent context\n- Enables local-first workflows" };

  const obsidian = exportKnowledge(article, annotations, summary, "obsidian");
  assert.match(obsidian, /title: "The Future of Open Protocols"/);
  assert.match(obsidian, /> \[!quote\] Highlight \(blue\)/);

  const roam = exportKnowledge(article, annotations, summary, "roam");
  assert.match(roam, /#\[\[Summary AI\]\]/);
  assert.match(roam, /#\[\[highlight\/blue\]\]/);

  const notion = exportKnowledge(article, annotations, summary, "notion");
  assert.match(notion, /## 🖍️ Highlights & Margin Notes/);

  const jsonRaw = exportKnowledge(article, annotations, summary, "json");
  const parsed = JSON.parse(jsonRaw);
  assert.equal(parsed.article.title, "The Future of Open Protocols");
  assert.equal(parsed.annotations.length, 1);
});

test("Sprint 1: chunkArticleIntoPassages and findExactPassages return exact character offsets", () => {
  const textContent = [
    "First paragraph introduces the history of hypertext systems in the late twentieth century.",
    "Second paragraph explains that photosynthesis in marine phytoplankton generates over half of Earth's oxygen supply.",
    "Third paragraph discusses how Model Context Protocol servers expose structured tools to autonomous agents."
  ].join("\n\n");

  const article = {
    id: "art_bio",
    title: "Science & Computing Compendium",
    url: "https://example.com/compendium",
    textContent
  };

  const passages = chunkArticleIntoPassages(article);
  assert.equal(passages.length, 3);
  assert.equal(
    textContent.slice(passages[1].startOffset, passages[1].endOffset),
    passages[1].text
  );

  const matches = findExactPassages([article], "How much oxygen does marine phytoplankton generate?", 2);
  assert.ok(matches.length >= 1);
  assert.equal(matches[0].paragraphIndex, 1);
  assert.match(matches[0].text, /photosynthesis in marine phytoplankton/);
});
