import {
  DEFAULT_READER_SETTINGS,
  READER_FONTS,
  HIGHLIGHT_COLORS,
  TTS_VOICES,
  exportKnowledge
} from "@summary-ai/shared";
import { buildKaraokeWordTimeline, findWordAtTimestamp } from "@summary-ai/ai";

/**
 * Cross-Platform Mobile Controller (iOS & Android via React Native / Expo)
 * Manages mobile share-sheet URL ingestion, offline article caching,
 * adaptive reader typography (including OpenDyslexic), background Karaoke TTS,
 * and cross-device cloud sync.
 */
export class MobileReaderController {
  constructor({ serverUrl = "http://localhost:3333", fetchImpl = globalThis.fetch } = {}) {
    this.serverUrl = String(serverUrl).replace(/\/+$/, "");
    this.fetchImpl = fetchImpl;
    this.readerSettings = { ...DEFAULT_READER_SETTINGS };
    this.offlineLibrary = new Map();
    this.activeTimeline = null;
  }

  getSupportedTypography() {
    return {
      fonts: READER_FONTS,
      highlightColors: HIGHLIGHT_COLORS,
      voices: TTS_VOICES,
      currentSettings: this.readerSettings
    };
  }

  updateReaderSettings(partial = {}) {
    this.readerSettings = { ...this.readerSettings, ...partial };
    return this.readerSettings;
  }

  /**
   * Handles incoming shared URLs from iOS Share Extension or Android SEND Intent.
   */
  async handleShareSheetUrl(sharedUrl, { model = "claude-3-7-sonnet", summaryMode = "tldr" } = {}) {
    const res = await this.fetchImpl(`${this.serverUrl}/api/v1/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: sharedUrl,
        model,
        summaryMode,
        tags: ["mobile-share"]
      })
    });
    if (!res.ok) throw new Error(`Mobile ingest failed: HTTP ${res.status}`);
    const data = await res.json();
    if (data.article) {
      this.offlineLibrary.set(data.article.id, data.article);
    }
    return data;
  }

  prepareKaraokeAudio(article, { voiceId = "aria-us-f", speed = 1.0 } = {}) {
    this.activeTimeline = buildKaraokeWordTimeline(article.textContent || "", {
      voiceId,
      speed
    });
    return this.activeTimeline;
  }

  getHighlightedWordAt(timestampMs) {
    if (!this.activeTimeline) return null;
    return findWordAtTimestamp(this.activeTimeline, timestampMs);
  }

  exportArticleNotes(articleId, format = "obsidian") {
    const art = this.offlineLibrary.get(articleId);
    if (!art) throw new Error(`Offline article not found: ${articleId}`);
    return exportKnowledge(art, art.annotations || [], art.latestSummary || null, format);
  }
}
