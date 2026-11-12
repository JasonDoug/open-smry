/**
 * Summary AI — Distraction-Free Web Reader Application Controller.
 * Connects the Web Reader UI to the FastAPI backend:
 * - Anonymous Session & Customization State (7 Fonts, 3 Themes, Sliders, Margins)
 * - Multi-Mirror Racer Ingestion (Direct, Wayback, Google Cache, Jina, YouTube, Books)
 * - Source Race Telemetry Bar
 * - One-Click "Copy to LLMs" & "Save & File"
 * - AI Summarization (5 modes) & Verifiable Q&A (Critic Verified Quotes & Offsets)
 * - Streaming Conversational Chat (SSE)
 * - Hybrid RAG Library Search & Reading History
 */

const FONT_MAP = {
  inter: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
  georgia: "Georgia, 'Times New Roman', serif",
  merriweather: "'Merriweather', Georgia, serif",
  lora: "'Lora', Georgia, serif",
  "jetbrains-mono": "'JetBrains Mono', monospace",
  atkinson: "'Atkinson Hyperlegible', sans-serif",
  opendyslexic: "'OpenDyslexic', 'Comic Sans MS', sans-serif"
};

const state = {
  sessionId: localStorage.getItem("smry_session_id") || null,
  meta: null,
  currentDocument: null,
  activeTab: "summary",
  sessionSettings: null,
  apiKeys: {},
  chatThreadId: null,
  libraryFilter: "all",
  libraryDisplay: "cards",
  activeView: "reader",
  karaoke: null,
  chatMessages: [
    {
      role: "assistant",
      content: "Hello! I'm your reading assistant. Ask me anything about the loaded text, or ask for clarifications on concepts, citations, and themes."
    }
  ]
};

// UI Helpers
function showToast(message) {
  const el = document.getElementById("toast-notification");
  if (!el) return;
  el.textContent = message;
  el.classList.remove("hidden");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => el.classList.add("hidden"), 3200);
}

// Format FastAPI error details (which may be arrays or objects) into readable text.
function formatErrorDetail(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    return value
      .map((item) => (item && typeof item === "object" && item.msg ? String(item.msg) : String(item)))
      .join("; ");
  }
  if (value && typeof value === "object") {
    if (value.msg) return String(value.msg);
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return value == null ? "" : String(value);
}

async function apiFetch(endpoint, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(endpoint, { ...options, headers });
  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}`;
    try {
      const errData = await res.json();
      const detail = formatErrorDetail(errData.detail ?? errData.error);
      errorDetail = detail || errorDetail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

// Session & Preferences
async function initSession() {
  try {
    if (state.sessionId) {
      try {
        const session = await apiFetch(`/api/v1/sessions/${state.sessionId}`);
        applySettingsToUi(session.settings);
        state.sessionSettings = session.settings;
        return;
      } catch {
        // Stale session, re-create
      }
    }
    const created = await apiFetch("/api/v1/sessions/anonymous", {
      method: "POST",
      body: JSON.stringify(null)
    });
    state.sessionId = created.session_id;
    localStorage.setItem("smry_session_id", created.session_id);
    applySettingsToUi(created.settings);
    state.sessionSettings = created.settings;
  } catch (err) {
    console.warn("Session init fallback:", err);
  }
}

// Estimate token count (rough: ~4 chars per token).
function estimateTokens(text) {
  if (!text) return 0;
  return Math.ceil(String(text).length / 4);
}

// Show/hide processing indicator with optional token count.
function setProgress(indicatorId, tokenCountId, show, text, tokenCount) {
  const el = document.getElementById(indicatorId);
  const tcEl = document.getElementById(tokenCountId);
  if (!el) return;
  if (show) {
    const textEl = el.querySelector(".progress-text");
    if (textEl && text) textEl.textContent = text;
    if (tcEl) {
      tcEl.textContent = tokenCount != null ? `${tokenCount} tokens` : "";
      tcEl.style.display = tokenCount != null ? "inline" : "none";
    }
    el.classList.remove("hidden");
  } else {
    el.classList.add("hidden");
  }
}

// HTML escaping helper
function escapeHtml(unsafe) {
  return String(unsafe || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Client-side safety-net stripper: removes distraction/paywall/chrome elements
// that the backend sanitizer may have missed, so the reader stays clean.
// Matching is whole-token (class/id/role value equals one of these names), so
// article wrappers like "read-more", "post-modal-content", or
// "cookie-policy-article" are preserved while "ad-container" or "cookie-banner"
// are stripped.
const READER_DISTRACTION_TOKENS = new Set([
  "paywall", "paywall-overlay", "cookie", "cookie-banner", "cookie-consent",
  "cookie-settings", "consent", "consent-modal", "gdpr", "onetrust",
  "cybotcookiebot", "newsletter", "newsletter-modal", "newsletter-signup",
  "subscribe", "subscribe-wall", "subscription-wall", "meter-wall",
  "piano-modal", "reg-wall", "registration-wall", "ad", "ad-container",
  "ad-slot", "ad-wrapper", "advertisement", "sponsored", "sponsored-box",
  "popup", "popup-overlay", "modal-backdrop", "share-bar", "social-share",
  "related-posts", "outbrain", "taboola", "signup", "sign-in"
]);

function stripReaderExtras(container) {
  if (!container) return;
  let removed = 0;
  // Walk all elements and remove those whose class/id/role contains a
  // whole token matching a distraction keyword.
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_ELEMENT, {
    acceptNode(node) {
      if (!(node instanceof Element)) return NodeFilter.FILTER_SKIP;
      const tokens = [];
      for (const attr of ["class", "id", "role"]) {
        const value = node.getAttribute(attr);
        if (value) tokens.push(...value.toLowerCase().split(/\s+/));
      }
      if (tokens.some((t) => READER_DISTRACTION_TOKENS.has(t))) {
        return NodeFilter.FILTER_ACCEPT;
      }
      return NodeFilter.FILTER_SKIP;
    }
  });
  const toRemove = [];
  let node;
  while ((node = walker.nextNode())) toRemove.push(node);
  for (const el of toRemove) {
    el.remove();
    removed += 1;
  }
  // Remove empty <p>/<div> leftovers
  container.querySelectorAll("p, div, section").forEach((el) => {
    if (!el.querySelector("p, h1, h2, h3, h4, h5, h6, ul, ol, blockquote, img, table") && el.textContent.trim().length === 0) {
      el.remove();
    }
  });
  return removed;
}

// Render document into reader — prefers backend-sanitized content_html,
// falls back to text_content with basic markdown rendering.
function renderDocumentInReader(doc) {
  if (state.karaoke) stopKaraoke({ restore: false });
  state.currentDocument = doc;

  const kickerEl = document.getElementById("article-kicker");
  const titleEl = document.getElementById("article-title");
  const bylineEl = document.getElementById("article-byline");
  const statsBadge = document.getElementById("article-stats-badge");

  // Metadata & Byline
  const mediaType = (doc.media_type || "article").toUpperCase();
  const sourceName = (doc.source_used || "direct").toUpperCase();
  kickerEl.textContent = `${doc.site_name ? doc.site_name.toUpperCase() + " • " : ""}${mediaType} VIA ${sourceName}`;
  titleEl.textContent = doc.title || "Untitled Document";

  const bylineItems = [];
  if (doc.author) bylineItems.push(`By ${doc.author}`);
  if (doc.published_time) bylineItems.push(doc.published_time);
  bylineItems.push(`${doc.word_count || 0} words (~${doc.reading_time_minutes || 1} min read)`);
  // Build byline via DOM nodes so scraped metadata is never injected as HTML;
  // only render the source link when its protocol is http(s).
  bylineEl.textContent = "";
  bylineItems.forEach((item, idx) => {
    if (idx > 0) bylineEl.append("  •  ");
    bylineEl.append(item);
  });
  if (doc.url && /^https?:\/\//i.test(doc.url)) {
    bylineEl.append("  •  ");
    const link = document.createElement("a");
    link.href = doc.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = doc.url;
    bylineEl.appendChild(link);
  }

  // Stats badge
  statsBadge.textContent = `${doc.word_count || 0} words • ${doc.reading_time_minutes || 1}m read • ${doc.stripped_elements_count || 0} stripped`;

  // Render Telemetry Pills
  renderTelemetryPills(doc);

  // Flag paywalled previews so they aren't mistaken for the full article.
  const paywallNotice = document.getElementById("paywall-notice");
  if (paywallNotice) paywallNotice.classList.toggle("hidden", !doc.paywall_detected);

  renderArticleBody(doc);

  // Pre-fill / reset QA & Summary views
  const qaResults = document.getElementById("qa-results-box");
  if (qaResults) qaResults.classList.add("hidden");
  const summaryBox = document.getElementById("summary-output");
  if (summaryBox) {
    const safeTitle = doc.title || "Untitled Document";
    summaryBox.innerHTML = `<span class="muted-small">Ready to summarize "${escapeHtml(safeTitle.slice(0, 48))}...". Click "Generate Summary" above.</span>`;
  }
}

// Render the article body only — prefers pre-sanitized HTML from backend.
function renderArticleBody(doc) {
  const bodyEl = document.getElementById("article-body");
  bodyEl.innerHTML = "";
  const contentHtml = doc.content_html || "";
  if (contentHtml.trim()) {
    bodyEl.innerHTML = contentHtml;
  } else {
    const text = doc.text_content || "";
    const paragraphs = text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
    if (paragraphs.length === 0) {
      bodyEl.innerHTML = `<p class="muted-small">No text content extracted.</p>`;
    } else {
      bodyEl.innerHTML = paragraphs.map((p) => `<p>${escapeHtml(p)}</p>`).join("");
    }
  }

  // Client-side safety-net: strip distraction elements backend may have missed
  stripReaderExtras(bodyEl);
}

function renderTelemetryPills(doc) {
  const pillsContainer = document.getElementById("source-pills");
  if (!pillsContainer) return;
  pillsContainer.innerHTML = "";

  const attempts = doc.source_attempts || [];
  if (attempts.length === 0) {
    const pill = document.createElement("span");
    pill.className = "source-pill selected";
    pill.textContent = `✓ ${doc.source_used || "direct"}: ${doc.word_count || 0} words`;
    pillsContainer.appendChild(pill);
    return;
  }

  for (const attempt of attempts) {
    const pill = document.createElement("span");
    const isWinner = attempt.source === doc.source_used || attempt.selected;
    pill.className = `source-pill ${isWinner ? "selected" : ""}`;
    const wordCount = attempt.word_count ?? attempt.words ?? 0;
    const latency = attempt.latency_ms ?? attempt.latency ?? 0;
    pill.textContent = `${isWinner ? "✓ " : ""}${attempt.source}: ${wordCount}w (${latency}ms)`;
    pill.title = `Status: ${attempt.status || "ok"}${attempt.score ? ` • Score: ${attempt.score}` : ""}`;
    pillsContainer.appendChild(pill);
  }
}

// Lightweight Markdown -> HTML renderer (no build-step dependency)
function renderMarkdown(text) {
  if (!text) return "";
  let html = String(text);

  // Escape HTML first so user content is safe, then re-allow our generated tags
  html = html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Headers (must be before paragraphs)
  html = html.replace(/^### (.*$)/gim, "<h3>$1</h3>");
  html = html.replace(/^## (.*$)/gim, "<h2>$1</h2>");
  html = html.replace(/^# (.*$)/gim, "<h1>$1</h1>");

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Italic
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  // Inline code
  html = html.replace(/`(.+?)`/g, "<code>$1</code>");
  // Links — allow only http(s)/mailto schemes; other schemes stay plain text.
  // Input is pre-escaped, so attribute values are already HTML-safe.
  html = html.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (match, label, href) => {
    if (!/^(https?:\/\/|mailto:)/i.test(href)) return match;
    return `<a href="${href}" target="_blank" rel="noopener noreferrer">${label}</a>`;
  });

  // Bullet lists: convert lines starting with "- " into <li>, wrap consecutive ones in <ul>
  const lines = html.split("\n");
  const outLines = [];
  let inList = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (/^-\s+/.test(trimmed)) {
      const item = trimmed.replace(/^-\s+/, "");
      if (!inList) {
        outLines.push("<ul>");
        inList = true;
      }
      outLines.push(`<li>${item}</li>`);
    } else {
      if (inList) {
        outLines.push("</ul>");
        inList = false;
      }
      outLines.push(line);
    }
  }
  if (inList) outLines.push("</ul>");
  html = outLines.join("\n");

  // Paragraphs: split on blank lines, wrap non-empty blocks in <p> unless already a block tag
  const blocks = html.split(/\n\s*\n/);
  html = blocks
    .map((block) => {
      const trimmed = block.trim();
      if (!trimmed) return "";
      if (
        trimmed.startsWith("<h") ||
        trimmed.startsWith("<ul>") ||
        trimmed.startsWith("<li>") ||
        trimmed.startsWith("</ul>") ||
        trimmed.startsWith("<blockquote")
      ) {
        return trimmed;
      }
      return `<p>${trimmed.replace(/\n/g, "<br>")}</p>`;
    })
    .join("\n");

  return html;
}

// Actions: Extraction
async function handleExtractUrl(inputVal, sourceMode = "auto") {
  const btn = document.getElementById("extract-btn");
  btn.disabled = true;
  btn.textContent = "Extracting...";

  try {
    const isYouTube = /(?:youtube\.com\/(?:watch|shorts)|youtu\.be\/)/i.test(inputVal);
    let endpoint = "/api/v1/extract/url";
    let payload = { url: inputVal, source: sourceMode, save_to_library: true };

    if (isYouTube) {
      endpoint = "/api/v1/extract/youtube";
      payload = { url: inputVal, save_to_library: true };
    }

    const data = await apiFetch(endpoint, {
      method: "POST",
      body: JSON.stringify(payload)
    });

    const doc = data.document || data;
    renderDocumentInReader(doc);
    showToast(`Extracted via ${doc.source_used || "Direct"}`);
    refreshLibrary();
  } catch (err) {
    showToast(`Extraction error: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Read & Summarize";
  }
}

async function handleBookUpload(file) {
  const btn = document.getElementById("book-upload-btn");
  btn.disabled = true;
  btn.textContent = "Parsing...";

  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("save_to_library", "true");

    const data = await apiFetch("/api/v1/extract/book", {
      method: "POST",
      body: formData
    });

    const doc = data.document || data;
    renderDocumentInReader(doc);
    showToast(`Ingested book: ${doc.title}`);
    refreshLibrary();
  } catch (err) {
    showToast(`Book upload error: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "📖 Book";
  }
}

// Actions: Summarize & Verifiable Q&A
async function handleGenerateSummary() {
  if (!state.currentDocument) {
    showToast("Please load an article or book first.");
    return;
  }

  const [provider, model] = document.getElementById("ai-provider-select").value.split(":");
  const mode = document.getElementById("summary-mode-select").value;
  const customPrompt = document.getElementById("custom-prompt-input")?.value?.trim() || null;
  const btn = document.getElementById("generate-summary-btn");
  const outputBox = document.getElementById("summary-output");

  btn.disabled = true;
  btn.textContent = "Synthesizing...";
  outputBox.innerHTML = `<span class="muted-small">Agent synthesizing ${mode.toUpperCase()} summary with ${model}...</span>`;
  setProgress("summary-progress", "summary-token-count", true, "Generating summary…", null);

  const docText = state.currentDocument?.text_content || "";
  const inputTokens = estimateTokens(docText) + estimateTokens(customPrompt || "");

  try {
    const data = await apiFetch("/api/v1/summarize", {
      method: "POST",
      body: JSON.stringify({
        document_id: state.currentDocument.id,
        mode,
        provider,
        model,
        custom_prompt: mode === "custom" ? customPrompt : null,
        api_keys: state.apiKeys,
        session_id: state.sessionId
      })
    });

    const outputTokens = estimateTokens(data.content || "");
    setProgress("summary-progress", "summary-token-count", false, null, inputTokens + outputTokens);

    let html = `<strong>Mode: ${data.mode.toUpperCase()}</strong> (Saved ~${data.reading_time_saved_minutes} min read)`;
    html += renderMarkdown(data.content || "");
    if (data.key_points && data.key_points.length > 0) {
      html += `<h4>Key Takeaways:</h4><ul>${data.key_points.map((pt) => `<li>${renderMarkdown(pt)}</li>`).join("")}</ul>`;
    }
    outputBox.innerHTML = html;
    showToast("Summary synthesized!");
  } catch (err) {
    setProgress("summary-progress", "summary-token-count", false);
    outputBox.innerHTML = `<span style="color:#ef4444;">Error: ${err.message}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate Summary";
  }
}

async function handleVerifiableQa() {
  if (!state.currentDocument) {
    showToast("Please load an article or book first.");
    return;
  }
  const question = document.getElementById("qa-question-input").value.trim();
  if (!question) return;

  const btn = document.getElementById("qa-ask-btn");
  const resultsBox = document.getElementById("qa-results-box");
  btn.disabled = true;
  btn.textContent = "Checking...";
  resultsBox.classList.remove("hidden");
  resultsBox.innerHTML = `<span class="muted-small">Critic agent verifying quotes against passage index...</span>`;
  setProgress("qa-progress", "qa-token-count", true, "Checking passages…", null);

  const inputTokens = estimateTokens(state.currentDocument?.text_content || "") + estimateTokens(question);

  try {
    const [provider, model] = document.getElementById("ai-provider-select").value.split(":");
    const data = await apiFetch(`/api/v1/documents/${state.currentDocument.id}/ask`, {
      method: "POST",
      body: JSON.stringify({
        document_id: state.currentDocument.id,
        question,
        provider,
        model,
        api_keys: state.apiKeys,
        session_id: state.sessionId
      })
    });

    const outputTokens = estimateTokens(data.answer || "");
    setProgress("qa-progress", "qa-token-count", false, null, inputTokens + outputTokens);

    let html = `<div style="font-weight:600;margin-bottom:0.4rem;">Answer:</div><p style="margin:0 0 0.5rem 0;">${escapeHtml(data.answer)}</p>`;
    if (data.citations && data.citations.length > 0) {
      html += `<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;color:var(--accent-color);margin-top:0.5rem;">Verified Citations:</div>`;
      for (const cit of data.citations) {
        html += `
          <div class="citation-card">
            <em>"${escapeHtml(cit.exact_quote)}"</em>
            <div style="font-size:0.7rem;color:var(--text-secondary);margin-top:0.25rem;">
              Offsets: [chars ${escapeHtml(String(cit.start_char))}..${escapeHtml(String(cit.end_char))}] • Verified by Critic
            </div>
          </div>
        `;
      }
    }
    resultsBox.innerHTML = html;
  } catch (err) {
    setProgress("qa-progress", "qa-token-count", false);
    resultsBox.innerHTML = `<span style="color:#ef4444;">Error: ${err.message}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Ask";
  }
}

// Streaming Chat (SSE)
async function handleChatSend(e) {
  e.preventDefault();
  const inputEl = document.getElementById("chat-input");
  const text = inputEl.value.trim();
  if (!text) return;

  inputEl.value = "";
  const messagesBox = document.getElementById("chat-messages");

  // Append User message
  const userMsgEl = document.createElement("div");
  userMsgEl.className = "chat-msg user";
  userMsgEl.textContent = text;
  messagesBox.appendChild(userMsgEl);

  state.chatMessages.push({ role: "user", content: text });

  // Assistant placeholder
  const assistantMsgEl = document.createElement("div");
  assistantMsgEl.className = "chat-msg assistant";
  assistantMsgEl.textContent = "Thinking...";
  messagesBox.appendChild(assistantMsgEl);
  messagesBox.scrollTop = messagesBox.scrollHeight;

  const [provider, model] = document.getElementById("ai-provider-select").value.split(":");
  setProgress("chat-progress", null, true, "Assistant is responding…", null);

  try {
    const res = await fetch("/api/v1/chat?stream=true", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thread_id: state.chatThreadId || null,
        document_id: state.currentDocument?.id || null,
        message: text,
        provider,
        model,
        api_keys: state.apiKeys,
        session_id: state.sessionId
      })
    });

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const errData = await res.json();
        detail = errData.detail || detail;
      } catch {
        // ignore
      }
      throw new Error(detail);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let accumulated = "";
    let buffer = "";

    assistantMsgEl.textContent = "";

    const processLine = (line) => {
      if (!line.startsWith("data: ")) return;
      const payload = line.slice(6).trim();
      if (payload === "[DONE]") return;
      try {
        const parsed = JSON.parse(payload);
        if (parsed.thread_id && !state.chatThreadId) {
          state.chatThreadId = parsed.thread_id;
        }
        if (parsed.token) {
          accumulated += parsed.token;
          assistantMsgEl.textContent = accumulated;
          messagesBox.scrollTop = messagesBox.scrollHeight;
        }
      } catch {
        // ignore non-json SSE lines
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      // Retain the incomplete trailing segment for the next read.
      buffer = lines.pop() ?? "";
      for (const line of lines) processLine(line.replace(/\r$/, ""));
    }
    // Flush the decoder and process any final buffered line.
    buffer += decoder.decode();
    if (buffer) processLine(buffer.replace(/\r$/, ""));
    state.chatMessages.push({ role: "assistant", content: accumulated });
  } catch (err) {
    assistantMsgEl.textContent = `Error: ${err.message}`;
  } finally {
    setProgress("chat-progress", null, false);
  }
}

// Main-area view switching: reader column ⇄ full library view.
function showMainView(view) {
  const reader = document.getElementById("reader-column");
  const library = document.getElementById("library-main-view");
  if (reader) reader.classList.toggle("hidden", view === "library");
  if (library) library.classList.toggle("hidden", view !== "library");
  state.activeView = view;
  if (view === "library") refreshLibrary();
}

// ---------------------------------------------------------------------------
// Karaoke TTS: synthesize with word timings, highlight words in real time,
// click any word to seek audio to that timestamp.
// ---------------------------------------------------------------------------

function stopKaraoke({ restore = true } = {}) {
  if (state.karaoke) {
    if (state.karaoke.audio) {
      state.karaoke.audio.pause();
      state.karaoke.audio.src = "";
    }
    state.karaoke = null;
  }
  document.getElementById("karaoke-player").classList.add("hidden");
  const toggleBtn = document.getElementById("karaoke-toggle-btn");
  if (toggleBtn) toggleBtn.textContent = "🔊 Listen";
  const statusEl = document.getElementById("karaoke-status");
  if (statusEl) statusEl.textContent = "";
  if (restore && state.currentDocument) {
    // Body only: keep any displayed summary / Q&A answer intact.
    renderArticleBody(state.currentDocument);
  }
}

// Backend offsets are Python code-point indices; JS strings index UTF-16 units.
// Returns a converter for monotonically increasing UTF-16 indices (O(n) total).
function makeCodePointCounter(text) {
  let u16 = 0;
  let cp = 0;
  return (index) => {
    while (u16 < index) {
      const code = text.charCodeAt(u16);
      // A high surrogate followed by a low surrogate is one code point.
      if (code >= 0xd800 && code <= 0xdbff && u16 + 1 < text.length) {
        const next = text.charCodeAt(u16 + 1);
        if (next >= 0xdc00 && next <= 0xdfff) u16 += 1;
      }
      u16 += 1;
      cp += 1;
    }
    return cp;
  };
}

// Re-render the article as word spans. Timed words (those with a narration
// timestamp) are keyboard-operable buttons using a roving tabindex.
function renderKaraokeBody(doc, words) {
  const bodyEl = document.getElementById("article-body");
  const wordMap = new Map(words.map((w) => [w.char_start, w]));
  const text = doc.text_content || "";
  const toCp = makeCodePointCounter(text);
  const paragraphs = text.split(/\n\s*\n/);
  bodyEl.innerHTML = "";
  let cursor = 0;
  let firstTimed = null;

  for (const para of paragraphs) {
    const trimmedStart = text.indexOf(para, cursor);
    const p = document.createElement("p");
    p.className = "karaoke-para";
    if (trimmedStart >= 0) {
      // Slice with UTF-16 offsets; tag spans with code-point offsets.
      let local = trimmedStart;
      const wordRe = /\S+/g;
      let m;
      while ((m = wordRe.exec(para)) !== null) {
        const charStart = trimmedStart + m.index;
        const charEnd = charStart + m[0].length;
        if (charStart > local) {
          p.append(text.slice(local, charStart));
        }
        const cpStart = toCp(charStart);
        const cpEnd = toCp(charEnd);
        const span = document.createElement("span");
        span.className = "karaoke-word";
        span.dataset.cs = String(cpStart);
        span.dataset.ce = String(cpEnd);
        span.textContent = m[0];
        const w = wordMap.get(cpStart);
        if (w) {
          span.dataset.ms = String(w.start_ms);
          span.setAttribute("role", "button");
          span.tabIndex = firstTimed ? -1 : 0;
          if (!firstTimed) firstTimed = span;
        }
        p.appendChild(span);
        local = charEnd;
      }
      if (local < trimmedStart + para.length) {
        p.append(text.slice(local, trimmedStart + para.length));
      }
    } else {
      p.textContent = para;
    }
    bodyEl.appendChild(p);
    cursor = trimmedStart + para.length;
  }
}

// Start/resume karaoke playback. A rejected play() (autoplay policy, decode
// error) leaves the player usable with ▶ so the user can retry.
function playKaraoke() {
  if (!state.karaoke) return;
  state.karaoke.audio.play().catch((err) => {
    document.getElementById("karaoke-play-btn").textContent = "▶";
    showToast(`Playback blocked: ${err.message}. Press ▶ to retry.`);
  });
}

// Seek audio to a timed word span; untimed spans are ignored.
function seekKaraokeToSpan(span) {
  if (!state.karaoke || !span || span.dataset.ms === undefined) return;
  const ms = parseFloat(span.dataset.ms);
  if (!Number.isFinite(ms)) return;
  state.karaoke.audio.currentTime = ms / 1000;
  if (state.karaoke.audio.paused) playKaraoke();
}

// Move the single roving tab stop to `span` and focus it.
function focusKaraokeWord(span) {
  const current = document.querySelector('.karaoke-word[tabindex="0"]');
  if (current && current !== span) current.tabIndex = -1;
  span.tabIndex = 0;
  span.focus();
}

function highlightKaraokeWord() {
  if (!state.karaoke) return;
  const audio = state.karaoke.audio;
  const ms = audio.currentTime * 1000;
  const words = state.karaoke.words;
  // Binary search: last word whose start_ms <= current position.
  let lo = 0;
  let hi = words.length - 1;
  let active = null;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (words[mid].start_ms <= ms) {
      active = words[mid];
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  if (state.karaoke.activeEl) state.karaoke.activeEl.classList.remove("karaoke-active");
  if (active && active.end_ms >= ms - 3000) {
    const el = document.querySelector(`.karaoke-word[data-cs="${active.char_start}"]`);
    if (el) {
      el.classList.add("karaoke-active");
      state.karaoke.activeEl = el;
    }
  }
  // Scrubber + time readout
  const durationMs = Math.max(1, state.karaoke.durationMs || 0);
  document.getElementById("karaoke-scrubber").value = String(Math.round((ms / durationMs) * 1000));
  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  document.getElementById("karaoke-time").textContent =
    `${fmt(audio.currentTime)} / ${fmt((state.karaoke.durationMs || 0) / 1000)}`;
}

async function startKaraoke() {
  // Capture the document so a reader switch mid-request can't mix content.
  const doc = state.currentDocument;
  if (!doc || !doc.text_content) {
    showToast("Load an article or book first to listen.");
    return;
  }
  const text = doc.text_content.slice(0, 10000);
  // The selector is initialized from the session's preferred voice.
  const voiceId = document.getElementById("karaoke-voice-select")?.value || "aria-us-f";
  const btn = document.getElementById("karaoke-toggle-btn");
  const statusEl = document.getElementById("karaoke-status");
  btn.disabled = true;
  statusEl.textContent = "Synthesizing…";

  try {
    const data = await apiFetch("/api/v1/tts/synthesize", {
      method: "POST",
      body: JSON.stringify({
        text,
        voice_id: voiceId,
        speed: state.sessionSettings?.preferred_tts_speed || 1.0,
        session_id: state.sessionId
      })
    });

    if (state.currentDocument !== doc) {
      // User opened another document while synthesizing — discard.
      statusEl.textContent = "";
      return;
    }

    const audio = new Audio(`data:${data.mime_type};base64,${data.audio_base64}`);
    audio.playbackRate = parseFloat(document.getElementById("karaoke-speed-select").value) || 1.0;

    state.karaoke = {
      audio,
      words: data.words,
      durationMs: data.duration_ms,
      activeEl: null
    };

    renderKaraokeBody(doc, data.words);

    const playBtn = document.getElementById("karaoke-play-btn");
    audio.addEventListener("timeupdate", highlightKaraokeWord);
    audio.addEventListener("play", () => { playBtn.textContent = "⏸"; });
    audio.addEventListener("pause", () => { playBtn.textContent = "▶"; });
    audio.addEventListener("ended", () => {
      if (state.karaoke?.activeEl) state.karaoke.activeEl.classList.remove("karaoke-active");
      playBtn.textContent = "▶";
    });

    document.getElementById("karaoke-player").classList.remove("hidden");
    playBtn.textContent = "▶";
    btn.textContent = "⏹ Stop";
    statusEl.textContent = `${data.synthesis_engine} • ${data.words.length} words`;
  } catch (err) {
    showToast(`TTS error: ${err.message}`);
    statusEl.textContent = "";
    return;
  } finally {
    btn.disabled = false;
  }
  // Outside the TTS error path: a playback rejection is not a synthesis failure.
  playKaraoke();
}

// Library & History
function hostFromUrl(url) {
  try {
    return (new URL(url)).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function relTime(iso) {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w`;
  return `${Math.floor(days / 30)}mo`;
}

// Library list items are lightweight summaries (no content_html/text_content),
// so always fetch the full document before rendering it in the reader.
async function openLibraryDocument(documentId) {
  try {
    const doc = await apiFetch(`/api/v1/documents/${encodeURIComponent(documentId)}`);
    showMainView("reader");
    renderDocumentInReader(doc);
    showToast(`Loaded "${(doc.title || "Untitled Document").slice(0, 36)}..."`);
  } catch (err) {
    showToast(`Failed to open document: ${err.message}`);
  }
}

// Card / row "⋯" options menu (one shared popover).
function closeCardMenu() {
  const menu = document.getElementById("card-options-menu");
  if (!menu) return;
  menu.remove();
  document.querySelectorAll('.card-menu-btn[aria-expanded="true"]').forEach((b) => b.setAttribute("aria-expanded", "false"));
}

function openCardMenu(button, doc) {
  const wasOpen = button.getAttribute("aria-expanded") === "true";
  closeCardMenu();
  if (wasOpen) return;
  const menu = document.createElement("div");
  menu.id = "card-options-menu";
  menu.className = "card-options-menu";
  menu.setAttribute("role", "menu");
  const del = document.createElement("button");
  del.type = "button";
  del.className = "card-menu-item danger";
  del.setAttribute("role", "menuitem");
  del.textContent = "🗑 Delete";
  del.addEventListener("click", (e) => {
    e.stopPropagation();
    closeCardMenu();
    deleteLibraryDocument(doc);
  });
  menu.appendChild(del);
  document.body.appendChild(menu);
  const rect = button.getBoundingClientRect();
  menu.style.top = `${rect.bottom + window.scrollY + 4}px`;
  menu.style.left = `${Math.max(8, rect.right + window.scrollX - menu.offsetWidth)}px`;
  button.setAttribute("aria-expanded", "true");
  del.focus();
}

function buildCardMenuButton(doc) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "card-menu-btn";
  btn.title = "More options";
  btn.setAttribute("aria-label", `Options for ${doc.title || "document"}`);
  btn.setAttribute("aria-haspopup", "menu");
  btn.setAttribute("aria-expanded", "false");
  btn.textContent = "⋯";
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    openCardMenu(btn, doc);
  });
  return btn;
}

async function deleteLibraryDocument(doc) {
  const title = doc.title || "Untitled Document";
  if (!window.confirm(`Delete "${title}" from your library? This cannot be undone.`)) return;
  try {
    await apiFetch(`/api/v1/library/${encodeURIComponent(doc.id)}`, { method: "DELETE" });
    showToast(`Deleted "${title.slice(0, 36)}..."`);
    await refreshLibrary();
  } catch (err) {
    showToast(`Delete failed: ${err.message}`);
  }
}

// Smry-style library card: favicon cover, domain label, title, excerpt, meta.
function buildLibraryCard(doc) {
  const card = document.createElement("article");
  card.className = "library-card";
  const tags = Array.isArray(doc.tags) ? doc.tags : [];
  const tagHtml = tags.slice(0, 3).map((t) => `<span class="tag-chip">${escapeHtml(t)}</span>`).join("");
  const mediaIcon = doc.media_type === "youtube" ? "🎥" : doc.media_type === "book" ? "📖" : "📄";
  const host = doc.site_name || hostFromUrl(doc.url);
  const domain = (host || "saved").toUpperCase();
  const faviconUrl = hostFromUrl(doc.url)
    ? `https://www.google.com/s2/favicons?domain=${hostFromUrl(doc.url)}&sz=64`
    : "";
  const words = doc.word_count || 0;
  const mins = doc.reading_time_minutes || 1;
  const excerpt = (doc.excerpt || "").slice(0, 140);
  const age = relTime(doc.created_at || doc.updated_at);
  const thumb = doc.image_url
    ? `<img class="card-thumb" src="${escapeHtml(doc.image_url)}" alt="" loading="lazy"
        onerror="this.closest('.card-cover').classList.add('fallback'); this.remove();" />`
    : "";
  const faviconEl = faviconUrl
    ? `<img class="card-favicon" src="${escapeHtml(faviconUrl)}" alt="" loading="lazy" onerror="this.remove();" />`
    : "";
  card.innerHTML = `
    <div class="card-cover ${thumb ? "has-thumb" : ""}">
      ${thumb}
      ${faviconEl}
      ${thumb ? "" : `<span class="card-media-icon">${mediaIcon}</span>`}
    </div>
    <div class="card-body">
      <div class="card-meta">
        <span class="badge media-badge">${escapeHtml(doc.media_type)}</span>
        <span class="card-age">${escapeHtml(age)}</span>
      </div>
      <h3 class="card-title" title="${escapeHtml(doc.title || "")}">${escapeHtml(doc.title || "Untitled Document")}</h3>
      <div class="card-domain">${escapeHtml(domain)}</div>
      ${excerpt ? `<p class="card-excerpt">${escapeHtml(excerpt)}</p>` : ""}
      <div class="card-footer">
        <span class="card-stat"><span class="stat-icon">📝</span>${words} words</span>
        <span class="card-stat"><span class="stat-icon">⏱️</span>${mins}m</span>
        ${doc.author ? `<span class="card-stat"><span class="stat-icon">✍️</span>${escapeHtml(doc.author)}</span>` : ""}
      </div>
      ${tagHtml ? `<div class="card-tags">${tagHtml}</div>` : ""}
      <button type="button" class="btn-open-card" data-doc-id="${doc.id}">Open in Reader ↗</button>
    </div>
  `;
  card.querySelector("[data-doc-id]").addEventListener("click", () => openLibraryDocument(doc.id));
  card.querySelector(".card-cover").appendChild(buildCardMenuButton(doc));
  return card;
}

// Compact list row (smry "Display: List" mode).
function buildLibraryRow(doc) {
  const row = document.createElement("div");
  row.className = "library-row";
  const host = doc.site_name || hostFromUrl(doc.url);
  const faviconUrl = hostFromUrl(doc.url)
    ? `https://www.google.com/s2/favicons?domain=${hostFromUrl(doc.url)}&sz=32`
    : "";
  const age = relTime(doc.created_at || doc.updated_at);
  row.innerHTML = `
    <div class="row-favicon">${faviconUrl ? `<img src="${escapeHtml(faviconUrl)}" alt="" loading="lazy" onerror="this.remove();" />` : "📄"}</div>
    <div class="row-main">
      <div class="row-title">${escapeHtml(doc.title || "Untitled Document")}</div>
      <div class="row-sub">${escapeHtml(host || "")} • ${escapeHtml(doc.media_type)}</div>
    </div>
    <div class="row-meta">${escapeHtml(age)} • ${doc.word_count || 0}w</div>
    <button type="button" class="btn-tiny" data-doc-id="${doc.id}">Open ↗</button>
  `;
  row.querySelector("[data-doc-id]").addEventListener("click", () => openLibraryDocument(doc.id));
  row.appendChild(buildCardMenuButton(doc));
  return row;
}

async function refreshLibrary() {
  try {
    const libData = await apiFetch("/api/v1/library?limit=50");
    const countEl = document.getElementById("library-count");
    const items = libData.items || [];
    if (countEl) countEl.textContent = String(libData.total ?? items.length);

    const listEl = document.getElementById("library-items-list");
    listEl.innerHTML = "";

    if (items.length === 0) {
      listEl.innerHTML = `<div class="muted-small">Library is empty. Ingest an article or book to save it here.</div>`;
    } else {
      const activeFilter = state.libraryFilter || "all";
      const filtered = activeFilter === "all"
        ? items
        : items.filter((d) => (d.media_type || "article") === activeFilter);

      if (filtered.length === 0) {
        listEl.innerHTML = `<div class="muted-small">No ${activeFilter} documents saved yet.</div>`;
      } else if (state.libraryDisplay === "list") {
        for (const doc of filtered) listEl.appendChild(buildLibraryRow(doc));
      } else {
        for (const doc of filtered) listEl.appendChild(buildLibraryCard(doc));
      }
    }

    // Refresh history
    const histData = await apiFetch("/api/v1/history?limit=10");
    const histEl = document.getElementById("history-items-list");
    histEl.innerHTML = "";
    const histItems = histData.items || [];
    if (histItems.length === 0) {
      histEl.innerHTML = `<div class="muted-small">Reading history is empty.</div>`;
    } else {
      for (const item of histItems) {
        const card = document.createElement("div");
        card.className = "library-row";
        card.innerHTML = `
          <div class="row-favicon">🕘</div>
          <div class="row-main">
            <div class="row-title">${escapeHtml(item.title)}</div>
            <div class="row-sub">${escapeHtml(hostFromUrl(item.url) || "")} • ${item.word_count || 0} words</div>
          </div>
          <div class="row-meta">${escapeHtml(relTime(item.last_read_at))}</div>
        `;
        card.addEventListener("click", async () => {
          try {
            const doc = await apiFetch(`/api/v1/documents/${item.document_id}`);
            showMainView("reader");
            renderDocumentInReader(doc);
            showToast(`Reopened "${(doc.title || "Untitled Document").slice(0, 32)}..."`);
          } catch (err) {
            showToast(`Failed to open document: ${err.message}`);
          }
        });
        histEl.appendChild(card);
      }
    }
  } catch (err) {
    console.warn("Library refresh failed:", err);
  }
}

async function handleLibrarySearch() {
  const query = document.getElementById("library-search-input").value.trim();
  if (!query) return;

  const listEl = document.getElementById("library-items-list");
  listEl.innerHTML = `<div class="muted-small">Searching with hybrid BM25 + vector search...</div>`;

  try {
    const data = await apiFetch("/api/v1/library/search", {
      method: "POST",
      body: JSON.stringify({ query, limit: 10 })
    });

    listEl.innerHTML = "";
    if (data.passages.length === 0) {
      listEl.innerHTML = `<div class="muted-small">No passages matched "${escapeHtml(query)}".</div>`;
      return;
    }

    for (const res of data.passages) {
      const card = document.createElement("div");
      card.className = "library-card";
      card.innerHTML = `
        <strong>${escapeHtml(res.document_title || "Matching Passage")}</strong>
        <p style="margin:0.25rem 0;font-size:0.8rem;line-height:1.4;">"${escapeHtml((res.exact_quote || "").slice(0, 160))}..."</p>
        <div style="font-size:0.72rem;color:var(--text-secondary);display:flex;justify-content:space-between;align-items:center;">
          <span>Offsets [${escapeHtml(String(res.start_char))}..${escapeHtml(String(res.end_char))}]${res.offset_verified ? " • ✓ Verified" : ""}</span>
          <button type="button" class="btn-tiny" data-open-doc="${escapeHtml(res.document_id)}">Open Document</button>
        </div>
      `;
      card.querySelector("[data-open-doc]").addEventListener("click", async () => {
        try {
          const doc = await apiFetch(`/api/v1/documents/${res.document_id}`);
          showMainView("reader");
          renderDocumentInReader(doc);
          showToast(`Opened "${(doc.title || "Untitled Document").slice(0, 32)}..."`);
        } catch (err) {
          showToast(`Failed to open document: ${err.message}`);
        }
      });
      listEl.appendChild(card);
    }
  } catch (err) {
    listEl.innerHTML = `<div style="color:#ef4444;">Search error: ${escapeHtml(err.message)}</div>`;
  }
}

// Settings persistence
async function persistSettings(delta) {
  if (!state.sessionId) return;
  try {
    await apiFetch(`/api/v1/sessions/${state.sessionId}/settings`, {
      method: "PATCH",
      body: JSON.stringify(delta)
    });
  } catch (err) {
    console.error("Failed to persist settings:", err);
  }
}

async function persistApiKey(provider, key) {
  if (!state.sessionId) return;
  const keyMap = {
    claude: "anthropic_api_key",
    gpt: "openai_api_key",
    gemini: "gemini_api_key",
    openrouter: "openrouter_api_key"
  };
  const field = keyMap[provider];
  if (!field) return;
  const resp = await apiFetch(`/api/v1/sessions/${state.sessionId}/settings`, {
    method: "PATCH",
    body: JSON.stringify({ [field]: key })
  });
  if (resp && resp.settings) {
    state.sessionSettings = resp.settings;
  }
  state.apiKeys[provider] = key;
}

// Settings UI sync
function applySettingsToUi(settings) {
  if (!settings) return;
  // Theme
  document.documentElement.setAttribute("data-theme", settings.theme || "dark");
  document.querySelectorAll("#theme-buttons button").forEach((b) => {
    const isActive = b.dataset.themeVal === settings.theme;
    b.classList.toggle("active", isActive);
    b.setAttribute("aria-checked", String(isActive));
  });

  // Font
  const fontId = settings.font_id || "inter";
  document.body.setAttribute("data-font", fontId);
  const fontSelect = document.getElementById("font-family-select");
  if (fontSelect) fontSelect.value = fontId;

  // Font Size
  const size = settings.font_size_px || 18;
  const sizeInput = document.getElementById("font-size-range");
  const sizeLabel = document.getElementById("font-size-label");
  if (sizeInput) sizeInput.value = size;
  if (sizeLabel) sizeLabel.textContent = `${size}px`;
  const articleBody = document.getElementById("article-body");
  if (articleBody) articleBody.style.fontSize = `${size}px`;

  // Line Height
  const height = settings.line_height || 1.75;
  const heightInput = document.getElementById("line-height-range");
  const heightLabel = document.getElementById("line-height-label");
  if (heightInput) heightInput.value = height;
  if (heightLabel) heightLabel.textContent = String(height);
  if (articleBody) articleBody.style.lineHeight = String(height);

  // Margins
  const margin = settings.margin_width || "medium";
  const readerCol = document.getElementById("reader-column");
  if (readerCol) readerCol.setAttribute("data-margin", margin);
  document.querySelectorAll("#margin-buttons button").forEach((b) => {
    const isActive = b.dataset.marginVal === margin;
    b.classList.toggle("active", isActive);
    b.setAttribute("aria-checked", String(isActive));
  });

  // Narration voice: apply the session preference when it is a known option.
  const voiceSelect = document.getElementById("karaoke-voice-select");
  if (voiceSelect && settings.preferred_voice_id &&
      Array.from(voiceSelect.options).some((o) => o.value === settings.preferred_voice_id)) {
    voiceSelect.value = settings.preferred_voice_id;
  }

  // AI Provider & API Key status
  const providerSelect = document.getElementById("settings-ai-provider");
  if (providerSelect) providerSelect.value = settings.preferred_provider || "openrouter";
  const modelInput = document.getElementById("settings-ai-model");
  if (modelInput) modelInput.value = settings.preferred_model || "";
  const keyStatus = document.getElementById("settings-key-status");
  const apiKeyInput = document.getElementById("settings-api-key");
  const provider = settings.preferred_provider || "openrouter";
  const hasKey = {
    claude: settings.has_anthropic_key,
    gpt: settings.has_openai_key,
    gemini: settings.has_gemini_key,
    openrouter: settings.has_openrouter_key,
    ollama: true
  }[provider] || false;
  if (keyStatus) {
    keyStatus.textContent = hasKey ? "API key configured" : "No API key set";
    keyStatus.className = `key-status ${hasKey ? "configured" : "missing"}`;
  }
  if (apiKeyInput) apiKeyInput.value = "";
}

// Initial Wire-Up
async function init() {
  await initSession();

  // Load platform metadata
  try {
    state.meta = await apiFetch("/api/v1/meta");
  } catch (e) {
    console.warn("Meta fetch failed:", e);
  }

  // Populate dynamic providers if available
  try {
    const providersData = await apiFetch("/api/v1/models/providers");
    const providerSelect = document.getElementById("ai-provider-select");
    if (providerSelect && providersData.preset_models?.length > 0) {
      providerSelect.innerHTML = "";
      for (const m of providersData.preset_models) {
        const opt = document.createElement("option");
        opt.value = `${m.provider}:${m.id}`;
        opt.textContent = `${m.provider.toUpperCase()} • ${m.name || m.id}`;
        if (m.provider === "openrouter" && m.id === "openrouter/free") opt.selected = true;
        providerSelect.appendChild(opt);
      }
    }
  } catch {
    // Keep defaults
  }

  // Ingestion form submit
  document.getElementById("extract-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const val = document.getElementById("url-input").value.trim();
    const source = document.getElementById("source-select").value;
    if (val) handleExtractUrl(val, source);
  });

  // Book upload
  const fileInput = document.getElementById("book-file-input");
  document.getElementById("book-upload-btn").addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      handleBookUpload(fileInput.files[0]);
    }
  });

  // One-Click "Copy to LLMs"
  document.getElementById("copy-llm-btn").addEventListener("click", async () => {
    if (!state.currentDocument) {
      showToast("No article loaded. Load an article first.");
      return;
    }
    try {
      const data = await apiFetch(`/api/v1/documents/${state.currentDocument.id}/copy-to-llm`);
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(data.llm_markdown);
        showToast("Copied clean Markdown to clipboard for ChatGPT / Claude / Gemini!");
      } else {
        showToast("Markdown ready (clipboard API unavailable in insecure context)");
      }
    } catch (err) {
      showToast(`Copy error: ${err.message}`);
    }
  });

  // One-Click "Save & File"
  document.getElementById("save-library-btn").addEventListener("click", async () => {
    if (!state.currentDocument) {
      showToast("No article loaded. Ingest an article first.");
      return;
    }
    try {
      await apiFetch(`/api/v1/library/${state.currentDocument.id}`, { method: "POST" });
      showToast("Document saved & filed in Library!");
      refreshLibrary();
    } catch {
      showToast("Document already filed in Library!");
    }
  });

  // Settings Drawer Toggle (single button)
  document.getElementById("reader-settings-toggle").addEventListener("click", () => {
    document.getElementById("reader-settings-panel").classList.toggle("hidden");
  });

  // Sidebar Toggle for Mobile/Compact screens
  document.getElementById("sidebar-toggle-btn").addEventListener("click", () => {
    const sidebar = document.getElementById("assistant-sidebar");
    sidebar.classList.toggle("hidden");
  });

  // Theme Segmented Control
  document.querySelectorAll("#theme-buttons button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#theme-buttons button").forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-checked", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-checked", "true");
      const val = btn.dataset.themeVal;
      document.documentElement.setAttribute("data-theme", val);
      persistSettings({ theme: val });
    });
  });

  // Font Selection (7 Fonts)
  document.getElementById("font-family-select").addEventListener("change", (e) => {
    const fontId = e.target.value;
    document.body.setAttribute("data-font", fontId);
    persistSettings({ font_id: fontId });
  });

  // Font Size Slider
  const sizeInput = document.getElementById("font-size-range");
  sizeInput.addEventListener("input", (e) => {
    const px = parseInt(e.target.value, 10);
    document.getElementById("font-size-label").textContent = `${px}px`;
    document.getElementById("article-body").style.fontSize = `${px}px`;
  });
  sizeInput.addEventListener("change", (e) => {
    persistSettings({ font_size_px: parseInt(e.target.value, 10) });
  });

  // Line Height Slider
  const heightInput = document.getElementById("line-height-range");
  heightInput.addEventListener("input", (e) => {
    const val = parseFloat(e.target.value);
    document.getElementById("line-height-label").textContent = String(val);
    document.getElementById("article-body").style.lineHeight = String(val);
  });
  heightInput.addEventListener("change", (e) => {
    persistSettings({ line_height: parseFloat(e.target.value) });
  });

  // Margins Segmented Control
  document.querySelectorAll("#margin-buttons button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#margin-buttons button").forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-checked", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-checked", "true");
      const val = btn.dataset.marginVal;
      document.getElementById("reader-column").setAttribute("data-margin", val);
      persistSettings({ margin_width: val });
    });
  });

  // AI Provider dropdown
  const aiProviderSelect = document.getElementById("settings-ai-provider");
  if (aiProviderSelect) {
    aiProviderSelect.addEventListener("change", () => {
      const provider = aiProviderSelect.value;
      persistSettings({ preferred_provider: provider });
      const keyStatus = document.getElementById("settings-key-status");
      const hasKey = {
        claude: state.sessionSettings?.has_anthropic_key,
        gpt: state.sessionSettings?.has_openai_key,
        gemini: state.sessionSettings?.has_gemini_key,
        openrouter: state.sessionSettings?.has_openrouter_key,
        ollama: true
      }[provider] || false;
      if (keyStatus) {
        keyStatus.textContent = hasKey ? "API key configured" : "No API key set";
        keyStatus.className = `key-status ${hasKey ? "configured" : "missing"}`;
      }
    });
  }

  // Model input — save on change
  const aiModelInput = document.getElementById("settings-ai-model");
  if (aiModelInput) {
    aiModelInput.addEventListener("change", () => {
      persistSettings({ preferred_model: aiModelInput.value.trim() || null });
    });
  }

  // API key input - save on blur
  const apiKeyInput = document.getElementById("settings-api-key");
  if (apiKeyInput) {
    apiKeyInput.addEventListener("blur", async () => {
      const key = apiKeyInput.value.trim();
      if (!key) return;
      const provider = (document.getElementById("settings-ai-provider")?.value || "openrouter");
      try {
        await persistApiKey(provider, key);
        const keyStatus = document.getElementById("settings-key-status");
        if (keyStatus) {
          keyStatus.textContent = "API key configured";
          keyStatus.className = "key-status configured";
        }
        showToast(`API key saved for ${provider}`);
      } catch (err) {
        showToast(`Failed to save API key: ${err.message}`);
      }
    });
  }

  // Toggle API key visibility
  const keyToggle = document.getElementById("settings-api-key-toggle");
  if (keyToggle && apiKeyInput) {
    keyToggle.addEventListener("click", () => {
      const isPassword = apiKeyInput.type === "password";
      apiKeyInput.type = isPassword ? "text" : "password";
      keyToggle.textContent = isPassword ? "🙈" : "👁️";
    });
  }

  // Sidebar Tab Navigation (also swaps the main-area view)
  document.querySelectorAll(".sidebar-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".sidebar-tab").forEach((t) => {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });
      document.querySelectorAll(".sidebar-pane").forEach((p) => p.classList.remove("active"));

      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      const paneId = `pane-${tab.dataset.tab}`;
      const pane = document.getElementById(paneId);
      if (pane) pane.classList.add("active");

      // Library tab swaps the main area to the full library view;
      // Summary/Q&A and Chat tabs return to the reader.
      showMainView(tab.dataset.tab === "library" ? "library" : "reader");
    });
  });

  // "Open Full Library" button inside the sidebar library pane
  const openLibBtn = document.getElementById("open-library-main-btn");
  if (openLibBtn) {
    openLibBtn.addEventListener("click", () => showMainView("library"));
  }

  // Summary Style dropdown (show/hide custom prompt input)
  document.getElementById("summary-mode-select").addEventListener("change", (e) => {
    const wrap = document.getElementById("custom-prompt-wrap");
    if (e.target.value === "custom") {
      wrap.classList.remove("hidden");
    } else {
      wrap.classList.add("hidden");
    }
  });

  // AI Buttons
  document.getElementById("generate-summary-btn").addEventListener("click", handleGenerateSummary);
  document.getElementById("qa-ask-btn").addEventListener("click", handleVerifiableQa);
  document.getElementById("qa-question-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleVerifiableQa();
  });
  document.getElementById("chat-form").addEventListener("submit", handleChatSend);

  // Library & Search
  document.getElementById("library-search-btn").addEventListener("click", handleLibrarySearch);
  document.getElementById("library-search-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleLibrarySearch();
  });
  document.getElementById("refresh-library-btn").addEventListener("click", refreshLibrary);

  // Library filter chips (media type)
  document.querySelectorAll("#library-filter-chips button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#library-filter-chips button").forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-checked", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-checked", "true");
      state.libraryFilter = btn.dataset.filterVal;
      refreshLibrary();
    });
  });

  // Library display toggle (cards / list)
  const displayToggle = document.getElementById("library-display-toggle");
  if (displayToggle) {
    displayToggle.addEventListener("click", () => {
      state.libraryDisplay = state.libraryDisplay === "cards" ? "list" : "cards";
      displayToggle.textContent = state.libraryDisplay === "cards" ? "☰ List" : "▦ Cards";
      refreshLibrary();
    });
  }

  // Karaoke word-click seek: click any timed word to jump audio there.
  const articleBody = document.getElementById("article-body");
  articleBody.addEventListener("click", (e) => {
    const span = e.target.closest(".karaoke-word");
    if (span) seekKaraokeToSpan(span);
  });
  // Keyboard: Enter/Space seeks; arrow keys move the roving tab stop.
  articleBody.addEventListener("keydown", (e) => {
    const span = e.target.closest('.karaoke-word[role="button"]');
    if (!span || !state.karaoke) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      seekKaraokeToSpan(span);
    } else if (["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(e.key)) {
      e.preventDefault();
      const timed = Array.from(articleBody.querySelectorAll('.karaoke-word[role="button"]'));
      const idx = timed.indexOf(span);
      const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1;
      const target = timed[idx + step];
      if (target) focusKaraokeWord(target);
    }
  });

  // Close the card options menu on outside click / Escape / scroll.
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#card-options-menu")) closeCardMenu();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeCardMenu();
  });
  window.addEventListener("resize", closeCardMenu);
  // Capture phase: also close when an inner scroll container (library grid) scrolls.
  window.addEventListener("scroll", closeCardMenu, true);

  // Karaoke TTS controls
  document.getElementById("karaoke-toggle-btn").addEventListener("click", () => {
    if (state.karaoke) {
      stopKaraoke();
    } else {
      startKaraoke();
    }
  });

  const playBtn = document.getElementById("karaoke-play-btn");
  playBtn.addEventListener("click", () => {
    if (!state.karaoke) return;
    // Button label follows the audio's play/pause events.
    if (state.karaoke.audio.paused) {
      playKaraoke();
    } else {
      state.karaoke.audio.pause();
    }
  });

  document.getElementById("karaoke-back-btn").addEventListener("click", () => {
    if (state.karaoke) state.karaoke.audio.currentTime = Math.max(0, state.karaoke.audio.currentTime - 10);
  });
  document.getElementById("karaoke-fwd-btn").addEventListener("click", () => {
    if (state.karaoke) state.karaoke.audio.currentTime += 10;
  });

  document.getElementById("karaoke-speed-select").addEventListener("change", (e) => {
    if (state.karaoke) state.karaoke.audio.playbackRate = parseFloat(e.target.value);
  });

  const scrubber = document.getElementById("karaoke-scrubber");
  scrubber.addEventListener("input", (e) => {
    if (state.karaoke && state.karaoke.durationMs) {
      state.karaoke.audio.currentTime = (parseFloat(e.target.value) / 1000) * (state.karaoke.durationMs / 1000);
    }
  });

  document.getElementById("karaoke-close-btn").addEventListener("click", () => stopKaraoke());

  // Quickstart sample cards
  document.querySelectorAll(".quickstart-card").forEach((card) => {
    card.addEventListener("click", () => {
      const sampleUrl = card.dataset.sampleUrl;
      document.getElementById("url-input").value = sampleUrl;
      handleExtractUrl(sampleUrl, "auto");
    });
  });

  // Load Library on startup
  refreshLibrary();
}

// Start app on DOMContentLoaded
if (typeof window !== "undefined") {
  window.addEventListener("DOMContentLoaded", init);
}
