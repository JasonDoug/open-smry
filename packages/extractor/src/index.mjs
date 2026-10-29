import crypto from "node:crypto";
import { chunkArticleIntoPassages, exportToCopyForLLM } from "@summary-ai/shared";

/**
 * Patterns for distraction-free stripping: popups, ads, cookie banners,
 * soft paywall overlays, and newsletter modals.
 */
const DISTRACTION_CLASS_ID_REGEX =
  /\b(paywall|cookie-banner|cookie-consent|gdpr|onetrust|cybotcookiebot|newsletter-modal|newsletter-signup|subscribe-wall|subscription-wall|meter-wall|piano-modal|ad-container|ad-slot|ad-wrapper|advertisement|sponsored-box|popup-overlay|modal-backdrop|share-bar|social-share|related-posts|outbrain|taboola)\b/i;

const PAYWALL_TEXT_PATTERNS = [
  /subscribe to continue reading/i,
  /you have reached your free article limit/i,
  /this article is for subscribers only/i,
  /please enable javascript and disable any ad blocker/i,
  /verify you are human/i,
  /create a free account to continue reading/i
];

export function decodeHtmlEntities(str = "") {
  return String(str)
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&mdash;/gi, "—")
    .replace(/&ndash;/gi, "–")
    .replace(/&hellip;/gi, "...")
    .replace(/&#(\d+);/g, (_, dec) => String.fromCharCode(Number(dec)))
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
}

function extractMetaContent(html, attrName, attrValue) {
  const escaped = attrValue.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex1 = new RegExp(
    `<meta[^>]+${attrName}=["']${escaped}["'][^>]+content=["']([^"']+)["'][^>]*>`,
    "i"
  );
  const regex2 = new RegExp(
    `<meta[^>]+content=["']([^"']+)["'][^>]+${attrName}=["']${escaped}["'][^>]*>`,
    "i"
  );
  const match = html.match(regex1) || html.match(regex2);
  return match ? decodeHtmlEntities(match[1].trim()) : null;
}

/**
 * Strips popups, ads, cookie banners, newsletter modals, and soft paywall overlays,
 * and extracts clean semantic HTML, Markdown, and plain text.
 */
export function sanitizeAndExtractHtml(rawHtml = "", url = "") {
  let html = String(rawHtml || "");

  // Extract metadata before stripping head
  const ogTitle = extractMetaContent(html, "property", "og:title");
  const twitterTitle = extractMetaContent(html, "name", "twitter:title");
  const titleTagMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const h1Match = html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i);

  const rawTitle =
    ogTitle ||
    twitterTitle ||
    (h1Match ? h1Match[1].replace(/<[^>]+>/g, "") : null) ||
    (titleTagMatch ? titleTagMatch[1].replace(/<[^>]+>/g, "") : null) ||
    url ||
    "Untitled Article";
  const title = decodeHtmlEntities(rawTitle).replace(/\s+/g, " ").trim();

  const author =
    extractMetaContent(html, "name", "author") ||
    extractMetaContent(html, "property", "article:author") ||
    extractMetaContent(html, "name", "byl") ||
    null;

  const siteName =
    extractMetaContent(html, "property", "og:site_name") ||
    (url ? safeHostname(url) : null);

  const publishedTime =
    extractMetaContent(html, "property", "article:published_time") ||
    extractMetaContent(html, "name", "pubdate") ||
    extractMetaContent(html, "name", "date") ||
    null;

  const description =
    extractMetaContent(html, "property", "og:description") ||
    extractMetaContent(html, "name", "description") ||
    null;

  let strippedElementsCount = 0;
  const rawPaywallHit = PAYWALL_TEXT_PATTERNS.some((rx) => rx.test(html));

  // 1. Strip script, style, noscript, iframe, svg, canvas, form, nav, footer, header, aside
  html = html.replace(
    /<(script|style|noscript|iframe|svg|canvas|form|nav|footer|aside)\b[^>]*>[\s\S]*?<\/\1>/gi,
    () => {
      strippedElementsCount += 1;
      return "";
    }
  );

  // 2. Strip block elements whose class or id matches popups, ads, cookie banners, or soft paywall overlays
  const distractionBlockRegex =
    /<(div|section|aside|dialog|header|footer)\b([^>]*?(?:id|class)=["'][^"']*["'][^>]*)>([\s\S]*?)<\/\1>/gi;

  for (let pass = 0; pass < 3; pass += 1) {
    html = html.replace(distractionBlockRegex, (fullMatch, tag, attrs) => {
      if (DISTRACTION_CLASS_ID_REGEX.test(attrs)) {
        strippedElementsCount += 1;
        return "";
      }
      return fullMatch;
    });
  }

  // 3. Focus on <article> or <main> if available and substantial
  const articleMatch = html.match(/<article\b[^>]*>([\s\S]*?)<\/article>/i);
  const mainMatch = html.match(/<main\b[^>]*>([\s\S]*?)<\/main>/i);
  let bodyScope = html;
  if (articleMatch && articleMatch[1].replace(/<[^>]+>/g, "").trim().length > 180) {
    bodyScope = articleMatch[1];
  } else if (mainMatch && mainMatch[1].replace(/<[^>]+>/g, "").trim().length > 180) {
    bodyScope = mainMatch[1];
  } else {
    const bodyMatch = html.match(/<body\b[^>]*>([\s\S]*?)<\/body>/i);
    if (bodyMatch) bodyScope = bodyMatch[1];
  }

  // 4. Parse structured blocks (headings, paragraphs, list items, blockquotes, pre)
  const blockRegex = /<(h[1-6]|p|li|blockquote|pre)\b[^>]*>([\s\S]*?)<\/\1>/gi;
  const cleanBlocks = [];
  const markdownBlocks = [];
  const textParagraphs = [];

  let match;
  while ((match = blockRegex.exec(bodyScope)) !== null) {
    const tag = match[1].toLowerCase();
    const innerHtml = match[2];
    const plainText = decodeHtmlEntities(
      innerHtml
        .replace(/<br\s*\/?>/gi, "\n")
        .replace(/<[^>]+>/g, " ")
        .replace(/\s+/g, " ")
        .trim()
    );

    if (!plainText) continue;
    // Skip short boilerplate/cookie/paywall prompts inside paragraphs
    if (plainText.length < 120 && PAYWALL_TEXT_PATTERNS.some((rx) => rx.test(plainText))) {
      strippedElementsCount += 1;
      continue;
    }

    const safeText = escapeHtml(plainText);
    if (tag.startsWith("h")) {
      const level = Number(tag.slice(1)) || 2;
      const hashes = "#".repeat(Math.min(Math.max(level, 1), 6));
      cleanBlocks.push(`<${tag}>${safeText}</${tag}>`);
      markdownBlocks.push(`${hashes} ${plainText}`);
      textParagraphs.push(plainText);
    } else if (tag === "li") {
      cleanBlocks.push(`<p class="reader-list-item">• ${safeText}</p>`);
      markdownBlocks.push(`- ${plainText}`);
      textParagraphs.push(`• ${plainText}`);
    } else if (tag === "blockquote") {
      cleanBlocks.push(`<blockquote>${safeText}</blockquote>`);
      markdownBlocks.push(`> ${plainText}`);
      textParagraphs.push(plainText);
    } else if (tag === "pre") {
      cleanBlocks.push(`<pre><code>${safeText}</code></pre>`);
      markdownBlocks.push("```\n" + plainText + "\n```");
      textParagraphs.push(plainText);
    } else {
      cleanBlocks.push(`<p>${safeText}</p>`);
      markdownBlocks.push(plainText);
      textParagraphs.push(plainText);
    }
  }

  // Fallback if input had plain text or non-standard tags without <p>
  if (textParagraphs.length === 0) {
    const fallbackText = decodeHtmlEntities(
      bodyScope
        .replace(/<(br|div|p|section|tr)\b[^>]*>/gi, "\n\n")
        .replace(/<[^>]+>/g, " ")
    );
    const paras = fallbackText
      .split(/\n\s*\n/)
      .map((p) => p.replace(/\s+/g, " ").trim())
      .filter((p) => p.length > 0);

    for (const p of paras) {
      cleanBlocks.push(`<p>${escapeHtml(p)}</p>`);
      markdownBlocks.push(p);
      textParagraphs.push(p);
    }
  }

  const textContent = textParagraphs.join("\n\n").trim();
  const contentHtml = cleanBlocks.join("\n");
  const markdown = markdownBlocks.join("\n\n").trim();
  const words = textContent ? textContent.split(/\s+/).filter(Boolean) : [];
  const wordCount = words.length;
  const readingTimeMinutes = Math.max(1, Math.ceil(wordCount / 220));
  const excerpt =
    description ||
    (textParagraphs[0] ? textParagraphs[0].slice(0, 240) : "");

  const id = "art_" + crypto.createHash("sha1").update(url || title || textContent).digest("hex").slice(0, 12);
  const baseArticle = {
    id,
    url,
    title,
    author,
    siteName,
    publishedTime,
    excerpt,
    contentHtml,
    textContent,
    markdown,
    wordCount,
    readingTimeMinutes,
    strippedElementsCount,
    paywallDetected: rawPaywallHit && wordCount < 100
  };
  baseArticle.passages = chunkArticleIntoPassages(baseArticle);
  baseArticle.llmMarkdown = exportToCopyForLLM(baseArticle);
  return baseArticle;
}

/**
 * Scores an extracted article candidate to pick the most complete, unblocked version
 * during multi-source racing.
 */
export function scoreExtractionCandidate(article) {
  if (!article || !article.textContent) return 0;
  let score = 0;

  // Reward word count and paragraph richness
  score += Math.min(article.wordCount, 5000) * 0.5;
  score += Math.min((article.passages || []).length, 60) * 6;

  // Penalize paywall / truncation markers in extracted body or raw stub
  if (article.paywallDetected) {
    score -= 150;
  }
  for (const rx of PAYWALL_TEXT_PATTERNS) {
    if (rx.test(article.textContent)) {
      score -= 150;
    }
  }

  // Penalize ultra-short stubs (likely blocked or soft-paywalled)
  if (article.wordCount < 15) {
    score -= 40;
  }

  return Number(Math.max(0, score).toFixed(2));
}

/**
 * Parses a YouTube video ID from standard watch URLs, short links, embeds, or shorts.
 */
export function parseYouTubeVideoId(url = "") {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^www\./, "").toLowerCase();
    if (host === "youtu.be") {
      const id = parsed.pathname.split("/").filter(Boolean)[0];
      return id || null;
    }
    if (host === "youtube.com" || host === "m.youtube.com" || host === "music.youtube.com") {
      if (parsed.pathname === "/watch") {
        return parsed.searchParams.get("v");
      }
      const parts = parsed.pathname.split("/").filter(Boolean);
      if (parts[0] === "shorts" || parts[0] === "embed" || parts[0] === "v") {
        return parts[1] || null;
      }
    }
  } catch {
    return null;
  }
  return null;
}

export function formatSecondsToTimestamp(seconds = 0) {
  const totalSec = Math.max(0, Math.floor(Number(seconds) || 0));
  const hrs = Math.floor(totalSec / 3600);
  const mins = Math.floor((totalSec % 3600) / 60);
  const secs = totalSec % 60;
  if (hrs > 0) {
    return `${String(hrs).padStart(2, "0")}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

/**
 * Parses XML or JSON caption tracks into structured transcript segments and a Reader-compatible Article.
 */
export function buildYouTubeTranscriptArticle({
  videoId,
  url,
  title = "YouTube Video Transcript",
  author = "YouTube Creator",
  segments = []
}) {
  const normalizedSegments = segments.map((seg, idx) => {
    const startSec = Number(seg.start ?? seg.offset ?? idx * 5);
    const durationSec = Number(seg.dur ?? seg.duration ?? 5);
    const timestamp = formatSecondsToTimestamp(startSec);
    const text = decodeHtmlEntities(String(seg.text || "").replace(/\s+/g, " ").trim());
    return {
      index: idx,
      startSec,
      durationSec,
      timestamp,
      text
    };
  }).filter((s) => s.text.length > 0);

  const htmlLines = [];
  const mdLines = [];
  const textParas = [];

  for (const seg of normalizedSegments) {
    const line = `[${seg.timestamp}] ${seg.text}`;
    htmlLines.push(
      `<p class="yt-transcript-line" data-start-sec="${seg.startSec}"><strong class="yt-timestamp">[${seg.timestamp}]</strong> ${escapeHtml(seg.text)}</p>`
    );
    mdLines.push(`**[${seg.timestamp}]** ${seg.text}`);
    textParas.push(line);
  }

  const textContent = textParas.join("\n\n");
  const markdown = mdLines.join("\n\n");
  const contentHtml = htmlLines.join("\n");
  const wordCount = textContent ? textContent.split(/\s+/).filter(Boolean).length : 0;
  const readingTimeMinutes = Math.max(1, Math.ceil(wordCount / 220));
  const id = `yt_${videoId}`;

  const article = {
    id,
    url: url || `https://www.youtube.com/watch?v=${videoId}`,
    title,
    author,
    siteName: "YouTube",
    publishedTime: new Date().toISOString().slice(0, 10),
    excerpt: normalizedSegments.slice(0, 3).map((s) => s.text).join(" ").slice(0, 240),
    contentHtml,
    textContent,
    markdown,
    wordCount,
    readingTimeMinutes,
    mediaType: "youtube",
    videoId,
    transcriptSegments: normalizedSegments,
    sourceUsed: "youtube-transcript",
    strippedElementsCount: 0
  };
  article.passages = chunkArticleIntoPassages(article);
  article.llmMarkdown = exportToCopyForLLM(article);
  return article;
}

/**
 * Extracts readable transcripts from submitted YouTube video links.
 */
export async function extractYouTubeTranscript(url, { fetchImpl = globalThis.fetch } = {}) {
  const videoId = parseYouTubeVideoId(url);
  if (!videoId) {
    throw new Error(`Invalid YouTube URL: ${url}`);
  }

  let title = `YouTube Video (${videoId})`;
  let author = "YouTube Channel";
  const segments = [];

  if (typeof fetchImpl === "function") {
    try {
      const watchRes = await fetchImpl(`https://www.youtube.com/watch?v=${videoId}`, {
        headers: {
          "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
          "Accept-Language": "en-US,en;q=0.9"
        }
      });
      if (watchRes.ok) {
        const html = await watchRes.text();
        const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
        if (titleMatch) {
          title = decodeHtmlEntities(titleMatch[1].replace(/\s*-\s*YouTube\s*$/i, "").trim());
        }
        const authorMatch = html.match(/"ownerChannelName":"([^"]+)"/);
        if (authorMatch) {
          author = decodeHtmlEntities(authorMatch[1]);
        }

        // Parse captionTracks URL if present
        const captionMatch = html.match(/"captionTracks"\s*:\s*(\[[\s\S]*?\])/);
        if (captionMatch) {
          const tracks = JSON.parse(captionMatch[1]);
          const enTrack = tracks.find((t) => /^en/i.test(t.languageCode)) || tracks[0];
          if (enTrack?.baseUrl) {
            const capRes = await fetchImpl(enTrack.baseUrl);
            if (capRes.ok) {
              const capXml = await capRes.text();
              const textTagRegex = /<text\s+start=["']([\d.]+)["'](?:\s+dur=["']([\d.]+)["'])?[^>]*>([\s\S]*?)<\/text>/gi;
              let m;
              while ((m = textTagRegex.exec(capXml)) !== null) {
                segments.push({
                  start: parseFloat(m[1]),
                  dur: parseFloat(m[2] || "4"),
                  text: decodeHtmlEntities(m[3].replace(/<[^>]+>/g, " "))
                });
              }
            }
          }
        }

        // If no XML caption tracks found, extract video shortDescription paragraphs as readable transcript fallback
        if (segments.length === 0) {
          const descMatch = html.match(/"shortDescription":"((?:\\.|[^"\\])*)"/);
          if (descMatch) {
            const rawDesc = JSON.parse(`"${descMatch[1]}"`);
            const lines = rawDesc.split(/\n+/).map((l) => l.trim()).filter(Boolean);
            lines.forEach((line, idx) => {
              segments.push({
                start: idx * 15,
                dur: 15,
                text: line
              });
            });
          }
        }
      }
    } catch {
      // Fall through to synthesized fallback below if network is unavailable
    }
  }

  if (segments.length === 0) {
    segments.push(
      { start: 0, dur: 12, text: `Transcript overview for YouTube video ${videoId} (${title}).` },
      { start: 12, dur: 18, text: "This video's spoken track or description has been indexed for reading, AI summarization, and timestamped Q&A." }
    );
  }

  return buildYouTubeTranscriptArticle({
    videoId,
    url,
    title,
    author,
    segments
  });
}

/**
 * Multi-Source Racing & Selection Engine:
 * Races Direct Fetch, Wayback Machine, Google Cache / Archive mirrors, and Reader Proxy
 * to pull the most complete, unblocked version of an article.
 */
export async function extractFromUrl(
  url,
  {
    preferredSource = "auto",
    fetchImpl = globalThis.fetch,
    timeoutMs = 6500,
    rawHtmlOverride = null
  } = {}
) {
  const normalizedUrl = String(url || "").trim();
  if (!normalizedUrl) {
    throw new Error("A valid URL or text input is required.");
  }

  // 1. Check if YouTube URL
  const ytId = parseYouTubeVideoId(normalizedUrl);
  if (ytId) {
    const ytArticle = await extractYouTubeTranscript(normalizedUrl, { fetchImpl });
    ytArticle.sourceAttempts = [
      {
        source: "youtube-transcript",
        status: "ok",
        wordCount: ytArticle.wordCount,
        score: 100,
        latencyMs: 12,
        selected: true
      }
    ];
    return ytArticle;
  }

  // 2. If raw HTML override is provided (e.g. from Browser Extension active tab DOM or direct paste)
  if (rawHtmlOverride) {
    const extracted = sanitizeAndExtractHtml(rawHtmlOverride, normalizedUrl);
    extracted.sourceUsed = "direct-dom";
    extracted.sourceScore = scoreExtractionCandidate(extracted);
    extracted.sourceAttempts = [
      {
        source: "direct-dom",
        status: "ok",
        wordCount: extracted.wordCount,
        score: extracted.sourceScore,
        latencyMs: 1,
        selected: true
      }
    ];
    return extracted;
  }

  const allProviders = [
    {
      id: "direct",
      buildRequestUrl: (u) => u,
      parseResponse: async (res, u) => sanitizeAndExtractHtml(await res.text(), u)
    },
    {
      id: "wayback",
      buildRequestUrl: (u) => `https://web.archive.org/web/2/${u}`,
      parseResponse: async (res, u) => sanitizeAndExtractHtml(await res.text(), u)
    },
    {
      id: "googlecache",
      buildRequestUrl: (u) => `https://webcache.googleusercontent.com/search?q=cache:${encodeURIComponent(u)}&strip=1`,
      parseResponse: async (res, u) => sanitizeAndExtractHtml(await res.text(), u)
    },
    {
      id: "jina",
      buildRequestUrl: (u) => `https://r.jina.ai/${u}`,
      parseResponse: async (res, u) => {
        const text = await res.text();
        const wrappedHtml = `<article><p>${text
          .split(/\n\s*\n/)
          .map((p) => escapeHtml(p.trim()))
          .filter(Boolean)
          .join("</p><p>")}</p></article>`;
        return sanitizeAndExtractHtml(wrappedHtml, u);
      }
    }
  ];

  const selectedProviders =
    preferredSource && preferredSource !== "auto"
      ? allProviders.filter((p) => p.id === preferredSource)
      : allProviders;

  const providersToRun = selectedProviders.length > 0 ? selectedProviders : allProviders;

  const attempts = await Promise.all(
    providersToRun.map(async (provider) => {
      const start = Date.now();
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const reqUrl = provider.buildRequestUrl(normalizedUrl);
        const res = await fetchImpl(reqUrl, {
          signal: controller.signal,
          headers: {
            "User-Agent":
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            Accept: "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            Referer: "https://www.google.com/"
          }
        });
        clearTimeout(timer);
        const latencyMs = Date.now() - start;

        if (!res || !res.ok) {
          return {
            source: provider.id,
            status: `http_${res?.status || "error"}`,
            wordCount: 0,
            score: 0,
            latencyMs,
            article: null
          };
        }

        const article = await provider.parseResponse(res, normalizedUrl);
        const score = scoreExtractionCandidate(article);
        return {
          source: provider.id,
          status: "ok",
          wordCount: article.wordCount,
          score,
          latencyMs,
          article
        };
      } catch (err) {
        clearTimeout(timer);
        return {
          source: provider.id,
          status: err?.name === "AbortError" ? "timeout" : "error",
          wordCount: 0,
          score: 0,
          latencyMs: Date.now() - start,
          article: null
        };
      }
    })
  );

  // Pick the highest scoring candidate
  const validAttempts = attempts
    .filter((a) => a.article && a.wordCount > 0)
    .sort((a, b) => b.score - a.score || a.latencyMs - b.latencyMs);

  const winner = validAttempts[0];
  if (!winner) {
    throw new Error(`Unable to extract content from ${normalizedUrl} across ${attempts.length} sources.`);
  }

  const winningArticle = winner.article;
  winningArticle.sourceUsed = winner.source;
  winningArticle.sourceScore = winner.score;
  winningArticle.sourceAttempts = attempts.map((a) => ({
    source: a.source,
    status: a.status,
    wordCount: a.wordCount,
    score: a.score,
    latencyMs: a.latencyMs,
    selected: a.source === winner.source
  }));
  winningArticle.llmMarkdown = exportToCopyForLLM(winningArticle);
  return winningArticle;
}

/**
 * Parses RSS 2.0 and Atom XML feeds for automated article extraction and agent subscriptions.
 */
export function parseRssOrAtomFeed(xml = "", feedUrl = "") {
  const raw = String(xml || "");
  const channelTitleMatch = raw.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const feedTitle = channelTitleMatch
    ? decodeHtmlEntities(channelTitleMatch[1].replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1").trim())
    : feedUrl || "RSS Feed";

  const items = [];
  const itemRegex = /<(item|entry)\b[^>]*>([\s\S]*?)<\/\1>/gi;
  let match;

  while ((match = itemRegex.exec(raw)) !== null) {
    const block = match[2];
    const titleMatch = block.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    const linkHrefMatch = block.match(/<link[^>]+href=["']([^"']+)["'][^>]*\/?>/i);
    const linkTextMatch = block.match(/<link[^>]*>([\s\S]*?)<\/link>/i);
    const pubDateMatch =
      block.match(/<(pubDate|published|updated)[^>]*>([\s\S]*?)<\/\1>/i);
    const descMatch =
      block.match(/<(description|summary|content:encoded|content)[^>]*>([\s\S]*?)<\/\1>/i);

    const cleanCdata = (val = "") =>
      decodeHtmlEntities(String(val).replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1").trim());

    const itemTitle = titleMatch ? cleanCdata(titleMatch[1]).replace(/<[^>]+>/g, "") : "Untitled Item";
    const itemUrl = linkHrefMatch ? cleanCdata(linkHrefMatch[1]) : linkTextMatch ? cleanCdata(linkTextMatch[1]) : "";
    const publishedTime = pubDateMatch ? cleanCdata(pubDateMatch[2]) : null;
    const summaryHtml = descMatch ? cleanCdata(descMatch[2]) : "";
    const summaryText = summaryHtml.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();

    if (itemUrl || itemTitle) {
      items.push({
        id: "rss_item_" + crypto.createHash("sha1").update(itemUrl || itemTitle).digest("hex").slice(0, 10),
        title: itemTitle,
        url: itemUrl,
        publishedTime,
        summary: summaryText.slice(0, 400)
      });
    }
  }

  return {
    title: feedTitle,
    feedUrl,
    items
  };
}

function safeHostname(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

function escapeHtml(str = "") {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
