import test from "node:test";
import assert from "node:assert/strict";
import {
  sanitizeAndExtractHtml,
  extractFromUrl,
  parseYouTubeVideoId,
  extractYouTubeTranscript,
  parseRssOrAtomFeed
} from "../src/index.mjs";

test("Sprint 2: sanitizeAndExtractHtml strips popups, cookie banners, ads, and soft paywalls", () => {
  const noisyHtml = `
    <!DOCTYPE html>
    <html>
      <head>
        <title>Deep Learning in 2026 | TechJournal</title>
        <meta name="author" content="Elena Vance" />
        <meta property="og:site_name" content="TechJournal" />
      </head>
      <body>
        <div id="cookie-banner" class="gdpr-popup">Accept all cookies to continue</div>
        <div class="paywall-modal subscribe-wall">Subscribe to continue reading this premium story</div>
        <aside class="ad-container">Sponsored Advertisement</aside>
        <article>
          <h1>Deep Learning in 2026</h1>
          <p>Transformer architectures have evolved into modular agentic systems capable of verifying every citation against primary source passages.</p>
          <div class="newsletter-modal">Sign up for our daily newsletter!</div>
          <p>Researchers found that combining deterministic passage retrieval with multi-source extraction reduces hallucination rates by over 78 percent across technical benchmarks.</p>
        </article>
        <script>window.showPaywallOverlay();</script>
      </body>
    </html>
  `;

  const result = sanitizeAndExtractHtml(noisyHtml, "https://techjournal.example/deep-learning-2026");
  assert.equal(result.title, "Deep Learning in 2026");
  assert.equal(result.author, "Elena Vance");
  assert.equal(result.siteName, "TechJournal");
  assert.ok(result.strippedElementsCount >= 4, "Should strip script, cookie banner, paywall modal, ad, and newsletter");
  assert.doesNotMatch(result.textContent, /Accept all cookies/);
  assert.doesNotMatch(result.textContent, /Sponsored Advertisement/);
  assert.doesNotMatch(result.textContent, /daily newsletter/);
  assert.match(result.textContent, /modular agentic systems/);
  assert.match(result.llmMarkdown, /# Deep Learning in 2026/);
  assert.ok(result.passages.length >= 2);
});

test("Sprint 2: extractFromUrl races multiple sources and selects the unblocked version", async () => {
  const mockFetch = async (reqUrl) => {
    if (reqUrl.includes("web.archive.org")) {
      return {
        ok: true,
        status: 200,
        text: async () => `
          <html>
            <head><title>Unblocked Full Investigation</title></head>
            <body>
              <article>
                <h1>Unblocked Full Investigation</h1>
                <p>This is the complete historical snapshot retrieved from the Wayback Machine mirror containing the full investigative report without any paywall truncation.</p>
                <p>It includes detailed empirical evidence, methodology notes, and primary source interviews spanning twelve laboratories.</p>
                <p>Furthermore, open-source verification enables independent reproducibility across every cited dataset.</p>
              </article>
            </body>
          </html>
        `
      };
    }
    // Direct fetch simulates a truncated soft-paywall stub
    return {
      ok: true,
      status: 200,
      text: async () => `
        <html>
          <head><title>Unblocked Full Investigation</title></head>
          <body>
            <article>
              <p>Subscribe to continue reading. You have reached your free article limit.</p>
            </article>
          </body>
        </html>
      `
    };
  };

  const article = await extractFromUrl("https://news.example.com/investigation", {
    fetchImpl: mockFetch
  });

  assert.equal(article.sourceUsed, "wayback");
  assert.match(article.textContent, /complete historical snapshot retrieved from the Wayback Machine/);
  assert.ok(Array.isArray(article.sourceAttempts));
  const selectedAttempt = article.sourceAttempts.find((a) => a.selected);
  assert.equal(selectedAttempt.source, "wayback");
});

test("Sprint 2: YouTube URL detection and transcript extraction", async () => {
  assert.equal(parseYouTubeVideoId("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "dQw4w9WgXcQ");
  assert.equal(parseYouTubeVideoId("https://youtu.be/abc123XYZ99"), "abc123XYZ99");

  const mockYtFetch = async (reqUrl) => {
    if (reqUrl.includes("youtube.com/watch")) {
      return {
        ok: true,
        text: async () => `
          <html>
            <head><title>How Agentic RAG Works - YouTube</title></head>
            <body>
              <script>
                var ytInitialPlayerResponse = {
                  "videoDetails": {"ownerChannelName":"AI Engineering Lab"},
                  "captions": {
                    "playerCaptionsTracklistRenderer": {
                      "captionTracks": [{"baseUrl":"https://youtube.com/api/timedtext?v=test12345","languageCode":"en"}]
                    }
                  }
                };
              </script>
            </body>
          </html>
        `
      };
    }
    if (reqUrl.includes("api/timedtext")) {
      return {
        ok: true,
        text: async () => `
          <transcript>
            <text start="0.0" dur="5.2">Welcome to the deep dive on agentic reading and retrieval.</text>
            <text start="5.2" dur="6.8">Today we explore how exact passage offsets prevent hallucinations.</text>
          </transcript>
        `
      };
    }
    return { ok: false, status: 404 };
  };

  const ytArticle = await extractYouTubeTranscript("https://www.youtube.com/watch?v=test12345", {
    fetchImpl: mockYtFetch
  });

  assert.equal(ytArticle.mediaType, "youtube");
  assert.equal(ytArticle.title, "How Agentic RAG Works");
  assert.equal(ytArticle.author, "AI Engineering Lab");
  assert.equal(ytArticle.transcriptSegments.length, 2);
  assert.match(ytArticle.textContent, /\[00:00\] Welcome to the deep dive/);
  assert.match(ytArticle.textContent, /\[00:05\] Today we explore how exact passage offsets/);
});

test("Sprint 2: parseRssOrAtomFeed parses RSS 2.0 items", () => {
  const sampleRss = `
    <?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>Alignment Research Feed</title>
        <item>
          <title> Mechanistic Interpretability Advances </title>
          <link>https://alignment.example.org/mech-interp</link>
          <pubDate>Thu, 29 Oct 2026 10:00:00 GMT</pubDate>
          <description><![CDATA[<p>Sparse autoencoders reveal monosemantic features in frontier models.</p>]]></description>
        </item>
      </channel>
    </rss>
  `;
  const feed = parseRssOrAtomFeed(sampleRss, "https://alignment.example.org/rss.xml");
  assert.equal(feed.title, "Alignment Research Feed");
  assert.equal(feed.items.length, 1);
  assert.equal(feed.items[0].title, "Mechanistic Interpretability Advances");
  assert.equal(feed.items[0].url, "https://alignment.example.org/mech-interp");
});
