/**
 * @summary-ai/shared
 * Core domain models, reader customization constants, PKM exporters,
 * annotation filters, and exact-passage indexing/citation utilities.
 */

export const READER_FONTS = [
  {
    id: "inter",
    name: "Inter",
    family: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    category: "sans-serif",
    description: "Crisp modern sans-serif for screen legibility"
  },
  {
    id: "georgia",
    name: "Georgia",
    family: "Georgia, 'Times New Roman', serif",
    category: "serif",
    description: "Classic editorial serif with generous x-height"
  },
  {
    id: "merriweather",
    name: "Merriweather",
    family: "'Merriweather', Georgia, serif",
    category: "serif",
    description: "Warm long-form book serif designed for digital screens"
  },
  {
    id: "lora",
    name: "Lora",
    family: "'Lora', Georgia, serif",
    category: "serif",
    description: "Contemporary calligraphic serif ideal for essays"
  },
  {
    id: "jetbrains-mono",
    name: "JetBrains Mono",
    family: "'JetBrains Mono', 'Fira Code', monospace",
    category: "monospace",
    description: "Developer-friendly monospace for technical articles"
  },
  {
    id: "atkinson",
    name: "Atkinson Hyperlegible",
    family: "'Atkinson Hyperlegible', sans-serif",
    category: "accessibility",
    description: "High-distinction letterforms for low-vision accessibility"
  },
  {
    id: "opendyslexic",
    name: "OpenDyslexic",
    family: "'OpenDyslexic', 'Comic Sans MS', sans-serif",
    category: "accessibility",
    description: "Weighted bottoms to prevent letter rotation and aid dyslexic readers"
  }
];

export const DEFAULT_READER_SETTINGS = {
  theme: "dark", // "light" | "dark" | "sepia"
  fontId: "inter",
  fontSizePx: 18, // 14 - 28
  lineHeight: 1.75, // 1.3 - 2.2
  marginWidth: "medium" // "narrow" | "medium" | "wide"
};

export const HIGHLIGHT_COLORS = [
  { id: "yellow", label: "Amber Insight", hex: "#facc15", bg: "rgba(250, 204, 21, 0.28)" },
  { id: "green", label: "Emerald Fact", hex: "#34d399", bg: "rgba(52, 211, 153, 0.28)" },
  { id: "blue", label: "Sky Reference", hex: "#38bdf8", bg: "rgba(56, 189, 248, 0.28)" },
  { id: "purple", label: "Violet Concept", hex: "#c084fc", bg: "rgba(192, 132, 252, 0.28)" },
  { id: "coral", label: "Coral Question", hex: "#fb7185", bg: "rgba(251, 113, 133, 0.28)" }
];

export const EXTRACTION_SOURCES = [
  { id: "auto", name: "Auto Race (Fastest Unblocked)", description: "Races all mirrors and picks the most complete unblocked version" },
  { id: "direct", name: "Direct Fetch", description: "Fetches straight from the origin server with clean reader headers" },
  { id: "wayback", name: "Wayback Machine", description: "Queries Internet Archive snapshots" },
  { id: "googlecache", name: "Archive / Cache Mirror", description: "Queries cached text-only mirrors" },
  { id: "jina", name: "Reader Proxy Mirror", description: "Fetches via markdown reader proxy mirror" }
];

export const AI_MODELS = [
  {
    id: "claude-3-7-sonnet",
    provider: "claude",
    name: "Claude 3.7 Sonnet",
    badge: "Anthropic",
    description: "Nuanced synthesis, deep analytical reasoning, and faithful citations"
  },
  {
    id: "gpt-4o",
    provider: "gpt",
    name: "GPT-4o",
    badge: "OpenAI",
    description: "Fast multimodal reasoning and structured executive summaries"
  },
  {
    id: "gemini-2.5-pro",
    provider: "gemini",
    name: "Gemini 2.5 Pro",
    badge: "Google",
    description: "Long-context book & research synthesis with rapid recall"
  }
];

export const SUMMARY_MODES = [
  { id: "tldr", name: "Executive TL;DR", description: "2-3 sentence high-impact synthesis" },
  { id: "bullets", name: "Concise Bullet Points", description: "Scannable bulleted breakdown of core points" },
  { id: "takeaways", name: "Key Takeaways", description: "Actionable insights, thesis, and implications" },
  { id: "executive", name: "Deep Research Brief", description: "Structured briefing with context, arguments, and counterpoints" },
  { id: "custom", name: "Custom Prompt", description: "Driven by your own custom instructions" }
];

export const TTS_VOICES = [
  { id: "aria-us-f", name: "Aria", gender: "female", accent: "US English", lang: "en-US", pitch: 1.0, rateMultiplier: 1.0 },
  { id: "marcus-us-m", name: "Marcus", gender: "male", accent: "US English", lang: "en-US", pitch: 0.92, rateMultiplier: 0.98 },
  { id: "elena-uk-f", name: "Elena", gender: "female", accent: "British English", lang: "en-GB", pitch: 1.04, rateMultiplier: 1.0 },
  { id: "arthur-uk-m", name: "Arthur", gender: "male", accent: "British English", lang: "en-GB", pitch: 0.88, rateMultiplier: 0.96 },
  { id: "chloe-au-f", name: "Chloe", gender: "female", accent: "Australian English", lang: "en-AU", pitch: 1.02, rateMultiplier: 1.02 },
  { id: "liam-au-m", name: "Liam", gender: "male", accent: "Australian English", lang: "en-AU", pitch: 0.94, rateMultiplier: 1.0 },
  { id: "kavya-in-f", name: "Kavya", gender: "female", accent: "Indian English", lang: "en-IN", pitch: 1.05, rateMultiplier: 0.98 },
  { id: "rohan-in-m", name: "Rohan", gender: "male", accent: "Indian English", lang: "en-IN", pitch: 0.93, rateMultiplier: 0.97 },
  { id: "claire-eu-f", name: "Claire", gender: "female", accent: "Continental European", lang: "en-IE", pitch: 1.01, rateMultiplier: 0.99 },
  { id: "mateo-us-m", name: "Mateo", gender: "male", accent: "North American Broadcast", lang: "en-CA", pitch: 0.90, rateMultiplier: 1.01 }
];

/**
 * Formats an extracted article into clean, structured Markdown ready for ChatGPT, Claude, or Gemini ("Copy to LLMs").
 */
export function exportToCopyForLLM(article, options = {}) {
  const includePromptHeader = options.includePromptHeader !== false;
  const lines = [];
  if (includePromptHeader) {
    lines.push("Below is the full, clean text of an article extracted via Summary AI.");
    lines.push("Use this source text to answer questions, summarize, or analyze accurately with exact quotes.");
    lines.push("");
    lines.push("---");
    lines.push("");
  }
  lines.push(`# ${article.title || "Untitled Article"}`);
  lines.push("");
  const meta = [];
  if (article.url) meta.push(`- **Source URL:** ${article.url}`);
  if (article.siteName) meta.push(`- **Publication:** ${article.siteName}`);
  if (article.author) meta.push(`- **Author:** ${article.author}`);
  if (article.publishedTime) meta.push(`- **Published:** ${article.publishedTime}`);
  if (article.sourceUsed) meta.push(`- **Extracted Via:** ${article.sourceUsed}`);
  if (article.readingTimeMinutes) meta.push(`- **Reading Time:** ~${article.readingTimeMinutes} min (${article.wordCount || 0} words)`);
  if (meta.length > 0) {
    lines.push(...meta);
    lines.push("");
  }
  lines.push("---");
  lines.push("");
  lines.push((article.markdown || article.textContent || "").trim());
  return lines.join("\n");
}

/**
 * Filters and searches annotations by color tag and keyword query.
 */
export function filterAnnotations(annotations = [], { color = "all", query = "" } = {}) {
  const normalizedQuery = String(query || "").trim().toLowerCase();
  return annotations.filter((ann) => {
    if (color && color !== "all" && ann.color !== color) {
      return false;
    }
    if (!normalizedQuery) return true;
    const textMatch = String(ann.quote || "").toLowerCase().includes(normalizedQuery);
    const noteMatch = String(ann.note || "").toLowerCase().includes(normalizedQuery);
    return textMatch || noteMatch;
  });
}

/**
 * Exports article + highlights + notes + summary to Notion, Obsidian, Roam Research, Markdown, or JSON.
 */
export function exportKnowledge(article, annotations = [], summary = null, format = "markdown") {
  const fmt = String(format || "markdown").toLowerCase();
  const safeTitle = article?.title || "Untitled Article";
  const url = article?.url || "";
  const exportedAt = new Date().toISOString();

  if (fmt === "json") {
    return JSON.stringify(
      {
        schemaVersion: "1.0",
        exportedAt,
        article: {
          id: article?.id,
          title: safeTitle,
          url,
          author: article?.author || null,
          siteName: article?.siteName || null,
          publishedTime: article?.publishedTime || null,
          wordCount: article?.wordCount || 0
        },
        summary: summary || null,
        annotations: annotations.map((a) => ({
          id: a.id,
          quote: a.quote,
          note: a.note || "",
          color: a.color || "yellow",
          startOffset: a.startOffset ?? null,
          endOffset: a.endOffset ?? null,
          createdAt: a.createdAt
        }))
      },
      null,
      2
    );
  }

  if (fmt === "obsidian") {
    const tags = ["summary-ai", ...(article?.tags || [])].map((t) => `  - ${t}`).join("\n");
    const lines = [
      "---",
      `title: "${safeTitle.replace(/"/g, '\\"')}"`,
      `source: "${url}"`,
      `author: "${(article?.author || "Unknown").replace(/"/g, '\\"')}"`,
      `created: "${exportedAt.slice(0, 10)}"`,
      "tags:",
      tags,
      "---",
      "",
      `# ${safeTitle}`,
      ""
    ];
    if (url) lines.push(`> [!info] Metadata\n> - **URL:** ${url}\n> - **Author:** ${article?.author || "Unknown"}`);
    lines.push("");
    if (summary?.content) {
      lines.push("## AI Summary");
      lines.push(summary.content.trim());
      lines.push("");
    }
    lines.push("## Highlights & Margin Notes");
    if (annotations.length === 0) {
      lines.push("_No highlights recorded yet._");
    } else {
      for (const ann of annotations) {
        lines.push(`> [!quote] Highlight (${ann.color || "yellow"})`);
        lines.push(`> "${ann.quote}"`);
        if (ann.note) {
          lines.push(`>`);
          lines.push(`> **Note:** ${ann.note}`);
        }
        lines.push("");
      }
    }
    return lines.join("\n");
  }

  if (fmt === "roam") {
    const lines = [
      `- **${safeTitle}** #[[Summary AI]]`,
      `  - Source:: ${url || "Local Document"}`,
      `  - Author:: [[${article?.author || "Unknown"}]]`,
      `  - Exported:: [[${exportedAt.slice(0, 10)}]]`
    ];
    if (summary?.content) {
      lines.push("  - **AI Summary**");
      for (const line of summary.content.split("\n").filter(Boolean)) {
        lines.push(`    - ${line.replace(/^[-*]\s*/, "")}`);
      }
    }
    lines.push("  - **Highlights & Notes**");
    for (const ann of annotations) {
      lines.push(`    - "${ann.quote}" #[[highlight/${ann.color || "yellow"}]]`);
      if (ann.note) {
        lines.push(`      - **Note:** ${ann.note}`);
      }
    }
    return lines.join("\n");
  }

  if (fmt === "notion") {
    const lines = [
      `# ${safeTitle}`,
      `Property | Value`,
      `--- | ---`,
      `Source URL | ${url || "N/A"}`,
      `Author | ${article?.author || "Unknown"}`,
      `Exported Via | Summary AI`,
      ""
    ];
    if (summary?.content) {
      lines.push("## 💡 AI Summary");
      lines.push(summary.content.trim());
      lines.push("");
    }
    lines.push("## 🖍️ Highlights & Margin Notes");
    for (const ann of annotations) {
      lines.push(`> **${(ann.color || "yellow").toUpperCase()}**: "${ann.quote}"`);
      if (ann.note) {
        lines.push(`> 📝 *Margin Note:* ${ann.note}`);
      }
      lines.push("");
    }
    return lines.join("\n");
  }

  // Default: standard Markdown
  const lines = [
    `# ${safeTitle}`,
    "",
    url ? `- **Source:** [${url}](${url})` : "",
    article?.author ? `- **Author:** ${article.author}` : "",
    `- **Exported:** ${exportedAt}`,
    ""
  ].filter((l, i, arr) => !(l === "" && arr[i - 1] === ""));

  if (summary?.content) {
    lines.push("## Summary");
    lines.push("");
    lines.push(summary.content.trim());
    lines.push("");
  }

  lines.push("## Highlights & Notes");
  lines.push("");
  if (annotations.length === 0) {
    lines.push("_No highlights saved._");
  } else {
    for (const ann of annotations) {
      lines.push(`- **[${(ann.color || "yellow").toUpperCase()}]** "${ann.quote}"`);
      if (ann.note) {
        lines.push(`  - *Note:* ${ann.note}`);
      }
    }
  }
  return lines.join("\n");
}

/**
 * Splits an article's textContent into indexed passages with exact character offsets
 * so that later questions can cite the exact passage and character range.
 */
export function chunkArticleIntoPassages(article) {
  const fullText = String(article?.textContent || "");
  if (!fullText.trim()) return [];

  const rawBlocks = fullText.split(/\n\s*\n/);
  const passages = [];
  let cursor = 0;
  let index = 0;

  for (const rawBlock of rawBlocks) {
    const trimmed = rawBlock.trim();
    if (!trimmed) continue;
    const foundAt = fullText.indexOf(trimmed, cursor);
    const startOffset = foundAt >= 0 ? foundAt : cursor;
    const endOffset = startOffset + trimmed.length;
    cursor = endOffset;

    passages.push({
      id: `${article.id || "doc"}_p${index}`,
      articleId: article.id || "doc",
      articleTitle: article.title || "Untitled",
      articleUrl: article.url || "",
      paragraphIndex: index,
      startOffset,
      endOffset,
      text: trimmed
    });
    index += 1;
  }
  return passages;
}

const STOPWORDS = new Set([
  "the", "and", "for", "that", "this", "with", "from", "what", "when", "where",
  "which", "who", "whom", "whose", "why", "how", "are", "was", "were", "been",
  "being", "have", "has", "had", "does", "did", "will", "would", "should",
  "could", "can", "may", "might", "must", "shall", "into", "onto", "upon",
  "about", "above", "below", "between", "through", "during", "before", "after"
]);

export function tokenizeForSearch(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .filter((tok) => tok.length >= 2 && !STOPWORDS.has(tok));
}

/**
 * Retrieves the top matching passages with exact quotes and character offsets across one or more articles/books.
 */
export function findExactPassages(articles = [], query = "", topK = 5) {
  const queryTokens = tokenizeForSearch(query);
  const rawQueryLower = String(query || "").trim().toLowerCase();
  const allPassages = [];

  for (const art of articles) {
    const passages = Array.isArray(art.passages) && art.passages.length > 0
      ? art.passages
      : chunkArticleIntoPassages(art);
    allPassages.push(...passages);
  }

  if (allPassages.length === 0) return [];

  const scored = allPassages.map((passage) => {
    const lowerText = passage.text.toLowerCase();
    const passageTokens = tokenizeForSearch(passage.text);
    const tokenSet = new Set(passageTokens);

    let score = 0;
    let matchedTerms = 0;

    for (const qTok of queryTokens) {
      if (tokenSet.has(qTok)) {
        matchedTerms += 1;
        // Count frequency in passage
        const freq = passageTokens.filter((t) => t === qTok).length;
        score += 2.5 + Math.min(freq, 4) * 0.5;
      } else if (lowerText.includes(qTok)) {
        matchedTerms += 0.5;
        score += 1.2;
      }
    }

    // Exact phrase boost
    if (rawQueryLower.length > 3 && lowerText.includes(rawQueryLower)) {
      score += 8.0;
    }

    // Coverage ratio bonus
    if (queryTokens.length > 0) {
      score += (matchedTerms / queryTokens.length) * 3.0;
    }

    return {
      ...passage,
      score: Number(score.toFixed(3))
    };
  });

  scored.sort((a, b) => b.score - a.score || a.paragraphIndex - b.paragraphIndex);
  const positive = scored.filter((p) => p.score > 0);
  return (positive.length > 0 ? positive : scored).slice(0, topK);
}
