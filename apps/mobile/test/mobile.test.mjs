import test from "node:test";
import assert from "node:assert/strict";
import { MobileReaderController } from "../src/MobileReaderController.mjs";

test("Sprint 8 (Mobile): MobileReaderController handles share-sheet URLs, OpenDyslexic typography, and Karaoke TTS", async () => {
  const mockFetch = async () => ({
    ok: true,
    status: 201,
    json: async () => ({
      article: {
        id: "art_mob_1",
        title: "Mobile Research Paper",
        url: "https://example.org/mobile-paper",
        textContent: "Mobile edge inference accelerates local language models with low battery consumption.",
        annotations: [{ id: "a1", color: "purple", quote: "Mobile edge inference", note: "Edge NPU" }]
      },
      summary: { content: "**TL;DR:** Edge inference is fast and efficient." }
    })
  });

  const controller = new MobileReaderController({ fetchImpl: mockFetch });
  const typo = controller.getSupportedTypography();
  assert.equal(typo.fonts.length, 7);
  assert.ok(typo.fonts.some((f) => f.id === "opendyslexic"));

  const ingested = await controller.handleShareSheetUrl("https://example.org/mobile-paper");
  assert.equal(ingested.article.id, "art_mob_1");

  const timeline = controller.prepareKaraokeAudio(ingested.article, {
    voiceId: "chloe-au-f",
    speed: 1.25
  });
  assert.equal(timeline.voice.id, "chloe-au-f");
  const activeWord = controller.getHighlightedWordAt(timeline.words[2].startMs + 2);
  assert.equal(activeWord.index, 2);

  const obsidianExport = controller.exportArticleNotes("art_mob_1", "obsidian");
  assert.match(obsidianExport, /> \[!quote\] Highlight \(purple\)/);
});
