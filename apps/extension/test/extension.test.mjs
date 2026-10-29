import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildReaderRedirectUrl, quickSaveAndSummarizeTab } from "../src/background.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

test("Sprint 8 (Extension): Chromium MV3 and Firefox/Safari manifests are valid and quickSaveAndSummarizeTab works", async () => {
  const mv3 = JSON.parse(fs.readFileSync(path.join(__dirname, "../manifest.json"), "utf8"));
  const ff = JSON.parse(fs.readFileSync(path.join(__dirname, "../manifest.firefox.json"), "utf8"));

  assert.equal(mv3.manifest_version, 3);
  assert.ok(ff.browser_specific_settings.gecko.id);
  assert.ok(ff.browser_specific_settings.safari);

  const redirect = buildReaderRedirectUrl("https://example.com/story", "http://localhost:3333");
  assert.equal(redirect, "http://localhost:3333/?url=https%3A%2F%2Fexample.com%2Fstory");

  const mockFetch = async () => ({
    ok: true,
    status: 201,
    json: async () => ({
      article: { id: "art_ext_1", title: "Active Tab Story" },
      summary: { content: "**TL;DR:** Key takeaway from active tab." }
    })
  });

  const saved = await quickSaveAndSummarizeTab({
    tabUrl: "https://example.com/story",
    tabTitle: "Active Tab Story",
    fetchImpl: mockFetch
  });
  assert.equal(saved.article.id, "art_ext_1");
  assert.match(saved.summary.content, /TL;DR/);
});
