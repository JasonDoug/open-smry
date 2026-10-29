import test from "node:test";
import assert from "node:assert/strict";
import {
  generateSummary,
  contextualAskAi,
  askLibraryWithCitations,
  streamChatResponse,
  buildKaraokeWordTimeline,
  findWordAtTimestamp
} from "../src/index.mjs";

const SAMPLE_ARTICLE = {
  id: "art_quantum",
  title: "Fault-Tolerant Quantum Error Correction",
  url: "https://physics.example.org/qec-2026",
  wordCount: 120,
  readingTimeMinutes: 1,
  sourceUsed: "direct",
  textContent: [
    "Topological surface codes distribute quantum information across an array of physical qubits to protect logical states from local decoherence.",
    "Recent experiments demonstrated that magic state cultivation reduces the space-time overhead of fault-tolerant T-gates by an order of magnitude.",
    "Hardware architectures combining neutral atom arrays with reconfigurable optical tweezers enable transversal entangling gates with 99.9 percent fidelity."
  ].join("\n\n")
};

test("Sprint 4: generateSummary supports tldr, bullets, takeaways, executive, and custom prompt modes across Claude, GPT, and Gemini", async () => {
  const tldr = await generateSummary(SAMPLE_ARTICLE, { mode: "tldr", model: "claude-3-7-sonnet" });
  assert.equal(tldr.provider, "claude");
  assert.match(tldr.content, /TL;DR/);

  const bullets = await generateSummary(SAMPLE_ARTICLE, { mode: "bullets", model: "gpt-4o" });
  assert.equal(bullets.provider, "gpt");
  assert.match(bullets.content, /Concise Bullet Summary/);

  const custom = await generateSummary(SAMPLE_ARTICLE, {
    mode: "custom",
    model: "gemini-2.5-pro",
    customPrompt: "What fidelity do neutral atom arrays achieve?"
  });
  assert.equal(custom.provider, "gemini");
  assert.match(custom.content, /99\.9 percent fidelity/);
  assert.ok(custom.citations.length >= 1);
});

test("Sprint 4: contextualAskAi analyzes highlighted passages", async () => {
  const res = await contextualAskAi({
    article: SAMPLE_ARTICLE,
    selectionText: "magic state cultivation reduces the space-time overhead of fault-tolerant T-gates",
    action: "explain",
    model: "claude-3-7-sonnet"
  });
  assert.equal(res.provider, "claude");
  assert.match(res.answer, /magic state cultivation/);
  assert.ok(res.relatedPassages.length >= 1);
});

test("Sprint 4: askLibraryWithCitations returns exact passage and character offsets", async () => {
  const res = await askLibraryWithCitations({
    articles: [SAMPLE_ARTICLE],
    question: "How do neutral atom arrays perform entangling gates and at what fidelity?",
    model: "claude-3-7-sonnet"
  });
  assert.ok(res.citations.length >= 1);
  const topCitation = res.citations[0];
  assert.equal(topCitation.articleId, "art_quantum");
  assert.match(topCitation.quote, /99\.9 percent fidelity/);
  assert.equal(
    SAMPLE_ARTICLE.textContent.slice(topCitation.startOffset, topCitation.endOffset),
    topCitation.quote
  );
});

test("Sprint 4: streamChatResponse streams word-by-word tokens and citations", async () => {
  const events = [];
  for await (const ev of streamChatResponse({
    article: SAMPLE_ARTICLE,
    messages: [{ role: "user", content: "What protects logical states from local decoherence?" }],
    model: "gpt-4o"
  })) {
    events.push(ev);
  }
  const tokenEvents = events.filter((e) => e.type === "token");
  const doneEvent = events.find((e) => e.type === "done");
  assert.ok(tokenEvents.length > 5);
  assert.ok(doneEvent);
  assert.match(doneEvent.fullText, /Topological surface codes/);
});

test("Sprint 6: buildKaraokeWordTimeline & findWordAtTimestamp synchronize words with timestamps", () => {
  const timeline = buildKaraokeWordTimeline(SAMPLE_ARTICLE.textContent, {
    voiceId: "elena-uk-f",
    speed: 1.5
  });
  assert.equal(timeline.voice.id, "elena-uk-f");
  assert.equal(timeline.speed, 1.5);
  assert.ok(timeline.words.length > 30);

  const fifthWord = timeline.words[4];
  const lookedUp = findWordAtTimestamp(timeline, fifthWord.startMs + 5);
  assert.equal(lookedUp.index, 4);
  assert.equal(lookedUp.word, fifthWord.word);
});
