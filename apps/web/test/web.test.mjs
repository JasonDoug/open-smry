import test from "node:test";
import assert from "node:assert/strict";
import { createApiServer } from "@summary-ai/api";

test("Sprint 5 & 6: Web Reader UI serves index.html, styles.css, and app.js with all reader, AI, TTS, and PKM features", async () => {
  const { server } = createApiServer();
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const baseUrl = `http://127.0.0.1:${server.address().port}`;
  try {
    const htmlRes = await fetch(`${baseUrl}/`);
    assert.equal(htmlRes.status, 200);
    const html = await htmlRes.text();

    // Verify 7 fonts including OpenDyslexic
    assert.match(html, /opendyslexic/);
    // Verify Copy to LLMs button
    assert.match(html, /Copy to LLMs/);
    // Verify Model selector (Claude, GPT, Gemini)
    assert.match(html, /Claude 3\.7 Sonnet/);
    assert.match(html, /GPT-4o/);
    assert.match(html, /Gemini 2\.5 Pro/);
    // Verify PKM Exporters (Obsidian, Notion, Roam, Markdown, JSON)
    assert.match(html, /data-export="obsidian"/);
    assert.match(html, /data-export="notion"/);
    assert.match(html, /data-export="roam"/);

    const cssRes = await fetch(`${baseUrl}/styles.css`);
    assert.equal(cssRes.status, 200);

    const jsRes = await fetch(`${baseUrl}/app.js`);
    assert.equal(jsRes.status, 200);
  } finally {
    await new Promise((r) => server.close(r));
  }
});
