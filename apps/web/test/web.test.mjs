import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { createWebServer } from "../server.mjs";

test("Sprint 5: Web Reader UI serves HTML with 7 fonts (incl. OpenDyslexic), 3 themes & Typography Controls", async () => {
  const { server } = createWebServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  const baseUrl = `http://127.0.0.1:${port}`;

  try {
    // 1. Verify index.html
    const res = await fetch(`${baseUrl}/`);
    assert.equal(res.status, 200);
    const contentType = res.headers.get("content-type");
    assert.match(contentType, /text\/html/);
    const html = await res.text();

    // Verify Brand & No-Account access
    assert.match(html, /summary\.ai/);
    assert.match(html, /No Account Required/);

    // Verify 7 Reader Fonts including OpenDyslexic
    assert.match(html, /value="inter"/);
    assert.match(html, /value="georgia"/);
    assert.match(html, /value="merriweather"/);
    assert.match(html, /value="lora"/);
    assert.match(html, /value="jetbrains-mono"/);
    assert.match(html, /value="atkinson"/);
    assert.match(html, /value="opendyslexic"/);
    assert.match(html, /fonts\.cdnfonts\.com\/css\/opendyslexic/);

    // Verify 3 Themes (Light, Sepia, Dark)
    assert.match(html, /data-theme-val="light"/);
    assert.match(html, /data-theme-val="sepia"/);
    assert.match(html, /data-theme-val="dark"/);

    // Verify Typography Customization Sliders & Controls
    assert.match(html, /id="font-size-range"/);
    assert.match(html, /id="line-height-range"/);
    assert.match(html, /id="margin-buttons"/);
    assert.match(html, /id="reader-settings-panel"/);

    // Verify Universal Ingestion (Source selector, URL input & Book Upload)
    assert.match(html, /id="source-select"/);
    assert.match(html, /value="auto"/);
    assert.match(html, /value="wayback"/);
    assert.match(html, /id="url-input"/);
    assert.match(html, /id="book-upload-btn"/);
    assert.match(html, /id="source-telemetry-bar"/);

    // Verify Actions: Copy to LLMs & Save to Library
    assert.match(html, /id="copy-llm-btn"/);
    assert.match(html, /Copy to LLMs/);
    assert.match(html, /id="save-library-btn"/);
    assert.match(html, /Save &amp; File/);

    // Verify AI Summary Styles, Verifiable Q&A & Streaming Chat
    assert.match(html, /id="ai-provider-select"/);
    assert.match(html, /id="summary-mode-select"/);
    assert.match(html, /id="qa-ask-btn"/);
    assert.match(html, /id="chat-form"/);
    assert.match(html, /id="library-search-input"/);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test("Sprint 5: Web Reader serves styles.css with themes, 7 reader fonts & responsive grid", async () => {
  const { server } = createWebServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  const baseUrl = `http://127.0.0.1:${port}`;

  try {
    const res = await fetch(`${baseUrl}/styles.css`);
    assert.equal(res.status, 200);
    const css = await res.text();

    // Verify Themes
    assert.match(css, /html\[data-theme="dark"\]/);
    assert.match(css, /html\[data-theme="light"\]/);
    assert.match(css, /html\[data-theme="sepia"\]/);

    // Verify 7 Font mappings
    assert.match(css, /body\[data-font="inter"\]/);
    assert.match(css, /body\[data-font="georgia"\]/);
    assert.match(css, /body\[data-font="merriweather"\]/);
    assert.match(css, /body\[data-font="lora"\]/);
    assert.match(css, /body\[data-font="jetbrains-mono"\]/);
    assert.match(css, /body\[data-font="atkinson"\]/);
    assert.match(css, /body\[data-font="opendyslexic"\]/);

    // Verify Margin configurations & layout
    assert.match(css, /data-margin="narrow"/);
    assert.match(css, /data-margin="medium"/);
    assert.match(css, /data-margin="wide"/);
    assert.match(css, /\.telemetry-bar/);
    assert.match(css, /\.source-pill\.selected/);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test("Sprint 5: Web Reader serves app.js containing client state and API handlers", async () => {
  const { server } = createWebServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  const baseUrl = `http://127.0.0.1:${port}`;

  try {
    const res = await fetch(`${baseUrl}/app.js`);
    assert.equal(res.status, 200);
    const js = await res.text();

    assert.match(js, /renderDocumentInReader/);
    assert.match(js, /handleExtractUrl/);
    assert.match(js, /handleBookUpload/);
    assert.match(js, /handleGenerateSummary/);
    assert.match(js, /handleVerifiableQa/);
    assert.match(js, /handleChatSend/);
    assert.match(js, /handleLibrarySearch/);
    assert.match(js, /copy-to-llm/);
    assert.match(js, /opendyslexic/);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test("Sprint 5: Web Server transparently proxies /api/* and /openapi.json to FastAPI backend", async () => {
  // Spin up a mock backend server to verify proxy behavior
  const mockBackend = http.createServer((req, res) => {
    if (req.url === "/api/v1/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "healthy", version: "1.0.0" }));
      return;
    }
    if (req.url === "/openapi.json") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ openapi: "3.1.0", info: { title: "Summary AI" } }));
      return;
    }
    res.writeHead(404);
    res.end();
  });

  await new Promise((resolve) => mockBackend.listen(0, "127.0.0.1", resolve));
  const backendPort = mockBackend.address().port;

  const { server } = createWebServer({ backendUrl: `http://127.0.0.1:${backendPort}` });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const webPort = server.address().port;
  const baseUrl = `http://127.0.0.1:${webPort}`;

  try {
    // 1. Health check proxy
    const healthRes = await fetch(`${baseUrl}/api/v1/health`);
    assert.equal(healthRes.status, 200);
    const healthData = await healthRes.json();
    assert.equal(healthData.status, "healthy");

    // 2. OpenAPI JSON proxy
    const specRes = await fetch(`${baseUrl}/openapi.json`);
    assert.equal(specRes.status, 200);
    const specData = await specRes.json();
    assert.equal(specData.openapi, "3.1.0");
  } finally {
    await new Promise((resolve) => server.close(resolve));
    await new Promise((resolve) => mockBackend.close(resolve));
  }
});
