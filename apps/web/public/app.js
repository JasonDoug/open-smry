const FONT_FAMILY_MAP = {
  inter: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
  georgia: "Georgia, 'Times New Roman', serif",
  merriweather: "'Merriweather', Georgia, serif",
  lora: "'Lora', Georgia, serif",
  "jetbrains-mono": "'JetBrains Mono', monospace",
  atkinson: "'Atkinson Hyperlegible', sans-serif",
  opendyslexic: "'OpenDyslexic', 'Comic Sans MS', sans-serif"
};

const state = {
  meta: null,
  currentArticle: null,
  annotations: [],
  activeColorFilter: "all",
  annotationQuery: "",
  selectedText: "",
  ttsTimeline: null,
  ttsPlaying: false,
  ttsCurrentMs: 0,
  ttsTimer: null,
  ttsVoiceId: "aria-us-f",
  ttsSpeed: 1.0,
  chatHistory: []
};

function showToast(message) {
  const el = document.getElementById("toast-notification");
  if (!el) return;
  el.textContent = message;
  el.classList.remove("hidden");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => el.classList.add("hidden"), 2800);
}

function formatMs(ms = 0) {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

/**
 * Renders the article into the Distraction-Free Reader with interactive word-by-word spans
 * so Karaoke TTS highlighting and click-any-word timestamp jumping work seamlessly.
 */
function renderArticleInReader(article) {
  state.currentArticle = article;
  state.annotations = article.annotations || [];
  state.chatHistory = article.chatMessages || [];

  document.getElementById("article-kicker").textContent =
    `${(article.siteName || "READER MODE").toUpperCase()} • EXTRACTED VIA ${(article.sourceUsed || "DIRECT").toUpperCase()}`;
  document.getElementById("article-title").textContent = article.title || "Untitled Article";

  const bylineParts = [];
  if (article.author) bylineParts.push(`By ${article.author}`);
  if (article.publishedTime) bylineParts.push(article.publishedTime);
  bylineParts.push(`${article.wordCount || 0} words (~${article.readingTimeMinutes || 1} min read)`);
  if (article.url) bylineParts.push(article.url);
  document.getElementById("article-byline").textContent = bylineParts.join("  •  ");

  document.getElementById("article-stats-badge").textContent =
    `${article.wordCount || 0} words • ${article.passages?.length || 0} indexed passages • ${article.strippedElementsCount || 0} distractions stripped`;

  // Render Source Race Telemetry Pills
  const pillsEl = document.getElementById("source-pills");
  pillsEl.innerHTML = "";
  const attempts = article.sourceAttempts || [
    { source: article.sourceUsed || "direct", status: "ok", wordCount: article.wordCount || 0, latencyMs: 12, selected: true }
  ];
  for (const att of attempts) {
    const pill = document.createElement("span");
    pill.className = `source-pill ${att.selected ? "selected" : ""}`;
    pill.textContent = `${att.selected ? "✓ " : ""}${att.source}: ${att.wordCount}w (${att.latencyMs}ms)`;
    pillsEl.appendChild(pill);
  }

  // Build interactive word spans per paragraph so every word is clickable for Karaoke TTS
  const bodyEl = document.getElementById("article-body");
  bodyEl.innerHTML = "";
  const paragraphs = String(article.textContent || "").split(/\n\s*\n/).filter(Boolean);
  let globalWordIdx = 0;

  for (const para of paragraphs) {
    const p = document.createElement("p");
    // Check if any saved highlight matches this paragraph
    const matchingAnn = (article.annotations || []).find((a) => a.quote && para.includes(a.quote));
    if (matchingAnn) {
      p.classList.add(`hl-${matchingAnn.color || "yellow"}`);
    }

    const tokens = para.split(/(\s+)/);
    for (const tok of tokens) {
      if (/^\s+$/.test(tok)) {
        p.appendChild(document.createTextNode(tok));
      } else if (tok.length > 0) {
        const span = document.createElement("span");
        span.className = "reader-word";
        span.dataset.wordIndex = String(globalWordIdx);
        span.textContent = tok;
        span.addEventListener("click", () => {
          seekTtsToWordIndex(Number(span.dataset.wordIndex));
        });
        p.appendChild(span);
        globalWordIdx += 1;
      }
    }
    bodyEl.appendChild(p);
  }

  renderAnnotationsSidebar();
  loadTtsTimelineForArticle();

  if (article.latestSummary?.content) {
    document.getElementById("summary-output").textContent = article.latestSummary.content;
  }
}

async function loadTtsTimelineForArticle() {
  if (!state.currentArticle) return;
  stopTtsPlayback();
  const data = await fetchJson("/api/v1/tts/timeline", {
    method: "POST",
    body: JSON.stringify({
      articleId: state.currentArticle.id,
      textContent: state.currentArticle.textContent,
      voiceId: state.ttsVoiceId,
      speed: state.ttsSpeed
    })
  });
  state.ttsTimeline = data.timeline;
  state.ttsCurrentMs = 0;
  updateTtsUi(0);
}

function updateTtsUi(currentMs) {
  const timeline = state.ttsTimeline;
  if (!timeline) return;
  const totalMs = timeline.totalDurationMs || 1;
  const clamped = Math.min(Math.max(0, currentMs), totalMs);
  state.ttsCurrentMs = clamped;

  document.getElementById("tts-time-label").textContent =
    `${formatMs(clamped)} / ${formatMs(totalMs)}`;
  document.getElementById("tts-scrubber").value = String(Math.round((clamped / totalMs) * 1000));

  // Find active word and highlight in reader
  const words = timeline.words || [];
  const active = words.find((w) => clamped >= w.startMs && clamped <= w.endMs) || null;

  document.querySelectorAll(".reader-word.karaoke-active").forEach((el) =>
    el.classList.remove("karaoke-active")
  );

  if (active) {
    document.getElementById("tts-active-word-badge").textContent =
      `🔊 "${active.word}" (Word #${active.index + 1}/${timeline.totalWords})`;
    const wordSpan = document.querySelector(`.reader-word[data-word-index="${active.index}"]`);
    if (wordSpan) {
      wordSpan.classList.add("karaoke-active");
    }
  } else if (!state.ttsPlaying) {
    document.getElementById("tts-active-word-badge").textContent = "Karaoke Sync Ready";
  }
}

function seekTtsToWordIndex(wordIndex) {
  if (!state.ttsTimeline?.words) return;
  const target = state.ttsTimeline.words[wordIndex];
  if (!target) return;
  updateTtsUi(target.startMs);
  showToast(`Jumped to "${target.word}" at ${formatMs(target.startMs)}`);
  if (!state.ttsPlaying) {
    startTtsPlayback();
  }
}

function startTtsPlayback() {
  if (!state.ttsTimeline) return;
  state.ttsPlaying = true;
  document.getElementById("tts-play-toggle").textContent = "⏸ Pause";

  // Trigger browser SpeechSynthesis if available
  if ("speechSynthesis" in window && state.currentArticle?.textContent) {
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(state.currentArticle.textContent.slice(0, 1200));
    utter.rate = state.ttsSpeed;
    window.speechSynthesis.speak(utter);
  }

  clearInterval(state.ttsTimer);
  const tickMs = 80;
  state.ttsTimer = setInterval(() => {
    const nextMs = state.ttsCurrentMs + tickMs;
    if (nextMs >= (state.ttsTimeline?.totalDurationMs || 0)) {
      stopTtsPlayback();
      updateTtsUi(0);
      return;
    }
    updateTtsUi(nextMs);
  }, tickMs);
}

function stopTtsPlayback() {
  state.ttsPlaying = false;
  document.getElementById("tts-play-toggle").textContent = "▶ Play";
  clearInterval(state.ttsTimer);
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

async function renderAnnotationsSidebar() {
  if (!state.currentArticle) return;
  const params = new URLSearchParams({
    color: state.activeColorFilter,
    q: state.annotationQuery
  });
  const data = await fetchJson(`/api/v1/articles/${state.currentArticle.id}/annotations?${params}`);
  const listEl = document.getElementById("annotations-list");
  document.getElementById("ann-count").textContent = String((state.currentArticle.annotations || []).length);
  listEl.innerHTML = "";

  if (data.annotations.length === 0) {
    listEl.innerHTML = `<div class="muted-small">No matching highlights. Select any text in the article to highlight or attach a margin note.</div>`;
    return;
  }

  for (const ann of data.annotations) {
    const card = document.createElement("div");
    card.className = `annotation-card hl-${ann.color || "yellow"}`;
    card.innerHTML = `
      <div class="annotation-quote">"${ann.quote}"</div>
      ${ann.note ? `<div class="annotation-note">📝 ${ann.note}</div>` : ""}
      <div style="display:flex;justify-content:space-between;margin-top:0.4rem;">
        <span style="font-size:0.72rem;text-transform:uppercase;font-weight:700;">${ann.color}</span>
        <button type="button" class="btn-tiny" data-del-ann="${ann.id}">Delete</button>
      </div>
    `;
    card.querySelector("[data-del-ann]").addEventListener("click", async () => {
      await fetchJson(`/api/v1/articles/${state.currentArticle.id}/annotations/${ann.id}`, {
        method: "DELETE"
      });
      const refreshed = await fetchJson(`/api/v1/library/${state.currentArticle.id}`);
      renderArticleInReader(refreshed.article);
      showToast("Annotation removed");
    });
    listEl.appendChild(card);
  }
}

async function refreshLibraryAndFeeds() {
  const libData = await fetchJson("/api/v1/library");
  const libList = document.getElementById("library-items-list");
  libList.innerHTML = "";
  for (const item of libData.articles) {
    const div = document.createElement("div");
    div.className = "library-card";
    div.innerHTML = `
      <div style="font-weight:600;margin-bottom:0.25rem;">${item.title}</div>
      <div style="font-size:0.75rem;color:var(--text-secondary);margin-bottom:0.4rem;">
        ${item.wordCount || 0} words • ${(item.passages || []).length} passages • via ${item.sourceUsed || "direct"}
      </div>
      <div style="display:flex;gap:0.4rem;">
        <button type="button" class="btn-tiny" data-open-art="${item.id}">Open in Reader</button>
      </div>
    `;
    div.querySelector("[data-open-art]").addEventListener("click", () => {
      renderArticleInReader(item);
      showToast(`Loaded "${item.title}"`);
    });
    libList.appendChild(div);
  }

  const feedsData = await fetchJson("/api/v1/feeds");
  const feedsEl = document.getElementById("rss-feeds-list");
  feedsEl.innerHTML = "";
  for (const f of feedsData.feeds) {
    const card = document.createElement("div");
    card.className = "library-card";
    card.innerHTML = `<strong>${f.title}</strong> <span style="font-size:0.75rem;color:var(--text-secondary);">(${(f.items || []).length} items)</span>`;
    feedsEl.appendChild(card);
  }
}

async function refreshApiKeysList() {
  const data = await fetchJson("/api/v1/keys");
  const listEl = document.getElementById("api-keys-list");
  listEl.innerHTML = "";
  for (const k of data.keys) {
    const card = document.createElement("div");
    card.className = "library-card";
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
          <strong>${k.name}</strong> <code>${k.keyPrefix}</code>
          <div style="font-size:0.72rem;color:var(--text-secondary);">
            ${k.revokedAt ? "🚫 Revoked" : "✅ Active"} • Created ${k.createdAt.slice(0, 10)}
          </div>
        </div>
        ${
          !k.revokedAt
            ? `<button type="button" class="btn-tiny" data-revoke-key="${k.id}">Revoke</button>`
            : ""
        }
      </div>
    `;
    const btn = card.querySelector("[data-revoke-key]");
    if (btn) {
      btn.addEventListener("click", async () => {
        await fetchJson(`/api/v1/keys/${k.id}`, { method: "DELETE" });
        refreshApiKeysList();
        showToast("API Key revoked");
      });
    }
    listEl.appendChild(card);
  }
}

async function initApp() {
  state.meta = await fetchJson("/api/v1/meta");

  // Populate 10 Natural Voices dropdown
  const voiceSelect = document.getElementById("tts-voice-select");
  voiceSelect.innerHTML = "";
  for (const v of state.meta.ttsVoices) {
    const opt = document.createElement("option");
    opt.value = v.id;
    opt.textContent = `🎙️ ${v.name} (${v.accent} • ${v.gender})`;
    voiceSelect.appendChild(opt);
  }

  // Load initial library & default showcase article
  const libData = await fetchJson("/api/v1/library");
  if (libData.articles.length > 0) {
    renderArticleInReader(libData.articles[0]);
  }
  await refreshLibraryAndFeeds();

  // Wire URL / Text Extraction Form
  document.getElementById("extract-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const rawInput = document.getElementById("url-input").value.trim();
    const source = document.getElementById("source-select").value;
    if (!rawInput) return;

    const btn = document.getElementById("extract-btn");
    btn.textContent = "Extracting...";
    try {
      const isUrl = /^https?:\/\//i.test(rawInput);
      const payload = isUrl
        ? { url: rawInput, source, saveToLibrary: true }
        : { textContent: rawInput, title: rawInput.slice(0, 64), saveToLibrary: true };
      const { article } = await fetchJson("/api/v1/extract", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      renderArticleInReader(article);
      await refreshLibraryAndFeeds();
      showToast(`Extracted via ${article.sourceUsed}`);
    } catch (err) {
      showToast(`Extraction error: ${err.message}`);
    } finally {
      btn.textContent = "Read & Summarize";
    }
  });

  // Wire One-Click "Copy to LLMs"
  document.getElementById("copy-llm-btn").addEventListener("click", async () => {
    if (!state.currentArticle) return;
    const data = await fetchJson(`/api/v1/articles/${state.currentArticle.id}/export?format=llm`);
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(data.content);
    }
    showToast("Copied clean Markdown to clipboard for ChatGPT / Claude / Gemini!");
  });

  // Wire One-Click "Save & File" (Read, Summarize & File)
  document.getElementById("save-library-btn").addEventListener("click", async () => {
    if (!state.currentArticle) return;
    const model = document.getElementById("ai-model-select").value;
    const mode = document.getElementById("summary-mode-select").value;
    const { summary } = await fetchJson("/api/v1/summarize", {
      method: "POST",
      body: JSON.stringify({
        articleId: state.currentArticle.id,
        model,
        mode
      })
    });
    document.getElementById("summary-output").textContent = summary.content;
    await refreshLibraryAndFeeds();
    showToast("Article summarized, indexed & filed to Library!");
  });

  // Wire Reader Customization Drawer
  document.getElementById("reader-settings-toggle").addEventListener("click", () => {
    document.getElementById("reader-settings-panel").classList.toggle("hidden");
  });

  document.querySelectorAll("#theme-buttons button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#theme-buttons button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.documentElement.setAttribute("data-theme", btn.dataset.themeVal);
    });
  });

  document.getElementById("font-family-select").addEventListener("change", (e) => {
    const family = FONT_FAMILY_MAP[e.target.value] || FONT_FAMILY_MAP.inter;
    document.getElementById("reader-article").style.fontFamily = family;
  });

  document.getElementById("font-size-range").addEventListener("input", (e) => {
    const px = `${e.target.value}px`;
    document.getElementById("font-size-label").textContent = px;
    document.getElementById("reader-article").style.fontSize = px;
  });

  document.getElementById("line-height-range").addEventListener("input", (e) => {
    const lh = e.target.value;
    document.getElementById("line-height-label").textContent = lh;
    document.getElementById("reader-article").style.lineHeight = lh;
  });

  document.querySelectorAll("#margin-buttons button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#margin-buttons button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("reader-column").setAttribute("data-margin", btn.dataset.marginVal);
    });
  });

  // Wire Sidebar Tabs
  document.querySelectorAll(".sidebar-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".sidebar-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const target = tab.dataset.tab;
      document.querySelectorAll(".sidebar-pane").forEach((pane) => pane.classList.add("hidden"));
      document.getElementById(`pane-${target}`).classList.remove("hidden");
    });
  });

  // Wire Summary Mode & Generate Summary
  document.getElementById("summary-mode-select").addEventListener("change", (e) => {
    document
      .getElementById("custom-prompt-wrap")
      .classList.toggle("hidden", e.target.value !== "custom");
  });

  document.getElementById("generate-summary-btn").addEventListener("click", async () => {
    if (!state.currentArticle) return;
    const model = document.getElementById("ai-model-select").value;
    const mode = document.getElementById("summary-mode-select").value;
    const customPrompt = document.getElementById("custom-prompt-input").value.trim();
    const out = document.getElementById("summary-output");
    out.textContent = "Synthesizing summary...";
    const { summary } = await fetchJson("/api/v1/summarize", {
      method: "POST",
      body: JSON.stringify({
        articleId: state.currentArticle.id,
        model,
        mode,
        customPrompt
      })
    });
    out.textContent = summary.content;
  });

  // Wire Streaming AI Chat (SSE word-by-word streaming)
  document.getElementById("chat-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.currentArticle) return;
    const input = document.getElementById("chat-input");
    const question = input.value.trim();
    if (!question) return;
    input.value = "";

    const chatEl = document.getElementById("chat-messages");
    const userBubble = document.createElement("div");
    userBubble.className = "chat-bubble user";
    userBubble.textContent = question;
    chatEl.appendChild(userBubble);

    const assistantBubble = document.createElement("div");
    assistantBubble.className = "chat-bubble assistant";
    assistantBubble.textContent = "";
    chatEl.appendChild(assistantBubble);
    chatEl.scrollTop = chatEl.scrollHeight;

    state.chatHistory.push({ role: "user", content: question });
    const model = document.getElementById("ai-model-select").value;

    const response = await fetch("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        articleId: state.currentArticle.id,
        messages: state.chatHistory,
        model,
        stream: true
      })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";
      for (const frame of frames) {
        if (!frame.startsWith("data:")) continue;
        const jsonStr = frame.replace(/^data:\s*/, "");
        const ev = JSON.parse(jsonStr);
        if (ev.type === "token") {
          assistantBubble.textContent += ev.token;
          chatEl.scrollTop = chatEl.scrollHeight;
        }
      }
    }
  });

  // Wire Text Selection Popover for Multi-Color Highlights & Contextual Ask AI
  const popover = document.getElementById("selection-popover");
  document.getElementById("article-body").addEventListener("mouseup", (e) => {
    const sel = window.getSelection();
    const text = sel ? sel.toString().trim() : "";
    if (text.length < 4) {
      popover.classList.add("hidden");
      return;
    }
    state.selectedText = text;
    popover.style.left = `${Math.min(window.innerWidth - 330, Math.max(16, e.clientX - 120))}px`;
    popover.style.top = `${Math.max(16, e.clientY - 135)}px`;
    popover.classList.remove("hidden");
  });

  document.querySelectorAll("[data-hl-color]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!state.currentArticle || !state.selectedText) return;
      const color = btn.dataset.hlColor;
      const note = document.getElementById("selection-note-input").value.trim();
      await fetchJson(`/api/v1/articles/${state.currentArticle.id}/annotations`, {
        method: "POST",
        body: JSON.stringify({
          color,
          quote: state.selectedText,
          note
        })
      });
      document.getElementById("selection-note-input").value = "";
      popover.classList.add("hidden");
      const refreshed = await fetchJson(`/api/v1/library/${state.currentArticle.id}`);
      renderArticleInReader(refreshed.article);
      showToast(`Saved ${color} highlight!`);
    });
  });

  document.querySelectorAll("[data-context-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!state.currentArticle || !state.selectedText) return;
      const action = btn.dataset.contextAction;
      const model = document.getElementById("ai-model-select").value;
      popover.classList.add("hidden");
      const res = await fetchJson("/api/v1/ask-context", {
        method: "POST",
        body: JSON.stringify({
          articleId: state.currentArticle.id,
          selectionText: state.selectedText,
          action,
          model
        })
      });
      const chatEl = document.getElementById("chat-messages");
      const bubble = document.createElement("div");
      bubble.className = "chat-bubble assistant";
      bubble.textContent = res.answer;
      chatEl.appendChild(bubble);
      chatEl.scrollTop = chatEl.scrollHeight;
      showToast(`Contextual Ask AI (${action}) complete`);
    });
  });

  // Wire Annotation Filters & PKM Exports
  document.getElementById("annotation-search").addEventListener("input", (e) => {
    state.annotationQuery = e.target.value;
    renderAnnotationsSidebar();
  });

  document.querySelectorAll("#annotation-color-filters .color-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll("#annotation-color-filters .color-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.activeColorFilter = chip.dataset.color;
      renderAnnotationsSidebar();
    });
  });

  document.querySelectorAll("[data-export]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!state.currentArticle) return;
      const format = btn.dataset.export;
      const data = await fetchJson(`/api/v1/articles/${state.currentArticle.id}/export?format=${format}`);
      const preview = document.getElementById("export-preview");
      preview.textContent = data.content;
      preview.classList.remove("hidden");
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(data.content);
      }
      showToast(`Exported & copied ${format.toUpperCase()} format!`);
    });
  });

  // Wire Library Exact-Passage RAG Search
  document.getElementById("library-ask-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = document.getElementById("library-ask-input").value.trim();
    if (!question) return;
    const model = document.getElementById("ai-model-select").value;
    const data = await fetchJson("/api/v1/library/ask", {
      method: "POST",
      body: JSON.stringify({ question, model })
    });
    const out = document.getElementById("library-ask-output");
    const topCite = data.citations?.[0];
    out.innerHTML = `
      <div class="annotation-card" style="margin-top:0.5rem;">
        <div style="white-space:pre-wrap;margin-bottom:0.5rem;">${data.answer}</div>
        ${
          topCite
            ? `<div style="font-size:0.75rem;color:var(--accent-color);font-weight:600;">
                 Exact Passage Citation: ${topCite.articleTitle} (Paragraph ${topCite.paragraphIndex + 1}, chars ${topCite.startOffset}–${topCite.endOffset})
               </div>`
            : ""
        }
      </div>
    `;
  });

  // Wire RSS Subscription Form
  document.getElementById("rss-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const feedUrl = document.getElementById("rss-url-input").value.trim();
    if (!feedUrl) return;
    await fetchJson("/api/v1/feeds", {
      method: "POST",
      body: JSON.stringify({ feedUrl, autoIngestTop: 2 })
    });
    document.getElementById("rss-url-input").value = "";
    await refreshLibraryAndFeeds();
    showToast("Subscribed to RSS feed & ingested top articles!");
  });

  // Wire Cloud Sync button
  document.getElementById("sync-cloud-btn").addEventListener("click", async () => {
    const snap = await fetchJson("/api/v1/sync");
    showToast(`Cloud Sync verified (${snap.articles.length} articles synced at ${snap.syncedAt.slice(11, 19)})`);
  });

  // Wire Floating Audio Player & Karaoke Controls
  document.getElementById("tts-play-toggle").addEventListener("click", () => {
    if (state.ttsPlaying) stopTtsPlayback();
    else startTtsPlayback();
  });

  document.getElementById("tts-skip-back").addEventListener("click", () => {
    updateTtsUi(state.ttsCurrentMs - 10000);
  });

  document.getElementById("tts-skip-fwd").addEventListener("click", () => {
    updateTtsUi(state.ttsCurrentMs + 10000);
  });

  document.getElementById("tts-scrubber").addEventListener("input", (e) => {
    const totalMs = state.ttsTimeline?.totalDurationMs || 1;
    const ms = (Number(e.target.value) / 1000) * totalMs;
    updateTtsUi(ms);
  });

  document.getElementById("tts-voice-select").addEventListener("change", (e) => {
    state.ttsVoiceId = e.target.value;
    loadTtsTimelineForArticle();
  });

  document.getElementById("tts-speed-select").addEventListener("change", (e) => {
    state.ttsSpeed = Number(e.target.value);
    loadTtsTimelineForArticle();
  });

  // Wire Agents / API Keys Modal
  document.getElementById("agents-modal-toggle").addEventListener("click", () => {
    document.getElementById("agents-modal").classList.remove("hidden");
    refreshApiKeysList();
  });

  document.getElementById("agents-modal-close").addEventListener("click", () => {
    document.getElementById("agents-modal").classList.add("hidden");
  });

  document.getElementById("create-api-key-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const nameInput = document.getElementById("api-key-name-input");
    const { key } = await fetchJson("/api/v1/keys", {
      method: "POST",
      body: JSON.stringify({ name: nameInput.value.trim() })
    });
    nameInput.value = "";
    const banner = document.getElementById("new-key-banner");
    banner.textContent = `Save your new API Key now (shown once): ${key.apiKey}`;
    banner.classList.remove("hidden");
    refreshApiKeysList();
  });
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  window.addEventListener("DOMContentLoaded", () => {
    initApp().catch((err) => console.error("Summary AI init error:", err));
  });
}
