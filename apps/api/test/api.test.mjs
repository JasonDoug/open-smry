import test from "node:test";
import assert from "node:assert/strict";
import { createApiServer } from "../src/app.mjs";
import { SummaryStore } from "../src/store.mjs";

async function startTestServer() {
  const store = new SummaryStore();
  const { server } = createApiServer({ store });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const addr = server.address();
  const baseUrl = `http://127.0.0.1:${addr.port}`;
  return {
    baseUrl,
    store,
    close: () => new Promise((resolve) => server.close(resolve))
  };
}

test("Sprint 3 & 7: REST API supports OpenAPI 3.1, Ingest, Library Exact-Passage Q&A, Annotations, PKM Exports, RSS, and API Keys", async () => {
  const { baseUrl, close } = await startTestServer();
  try {
    // 1. Check OpenAPI 3.1 spec
    const openApiRes = await fetch(`${baseUrl}/openapi.json`);
    assert.equal(openApiRes.status, 200);
    const openApi = await openApiRes.json();
    assert.equal(openApi.openapi, "3.1.0");
    assert.ok(openApi.paths["/api/v1/library/ask"]);

    // 2. Save an article/book via /api/v1/ingest -> automatically read, summarized, and filed
    const ingestRes = await fetch(`${baseUrl}/api/v1/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: "https://research.example.org/solid-state-batteries",
        title: "Breakthroughs in Solid-State Lithium-Sulfur Batteries",
        textContent: [
          "Solid-state electrolytes eliminate flammable liquid solvents in next-generation battery cells.",
          "Researchers at the Energy Storage Institute achieved a specific energy density of 520 Wh/kg with zero dendrite propagation over 1,500 charge cycles.",
          "Manufacturing costs are projected to fall below $62 per kilowatt-hour using dry-electrode roll-to-roll calendering."
        ].join("\n\n"),
        tags: ["energy", "batteries"],
        model: "claude-3-7-sonnet",
        summaryMode: "bullets"
      })
    });
    assert.equal(ingestRes.status, 201);
    const { article, summary } = await ingestRes.json();
    assert.ok(article.id);
    assert.ok(summary.content);

    // 3. Ask a question later and get the answer with the exact passage
    const askRes = await fetch(`${baseUrl}/api/v1/library/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: "What specific energy density and cycle life did the Energy Storage Institute achieve?",
        model: "claude-3-7-sonnet"
      })
    });
    assert.equal(askRes.status, 200);
    const askData = await askRes.json();
    assert.ok(askData.citations.length >= 1);
    assert.match(askData.citations[0].quote, /520 Wh\/kg with zero dendrite propagation over 1,500 charge cycles/);

    // 4. Add multi-color annotation and export to Obsidian & Copy-to-LLM
    const annRes = await fetch(`${baseUrl}/api/v1/articles/${article.id}/annotations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        color: "green",
        quote: "520 Wh/kg with zero dendrite propagation over 1,500 charge cycles",
        note: "Key benchmark to cite in battery report"
      })
    });
    assert.equal(annRes.status, 201);

    const exportRes = await fetch(`${baseUrl}/api/v1/articles/${article.id}/export?format=obsidian`);
    assert.equal(exportRes.status, 200);
    const exportData = await exportRes.json();
    assert.match(exportData.content, /> \[!quote\] Highlight \(green\)/);

    // 5. Create, verify, and revoke API Key for agents
    const createKeyRes = await fetch(`${baseUrl}/api/v1/keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "CI Research Agent" })
    });
    assert.equal(createKeyRes.status, 201);
    const { key } = await createKeyRes.json();
    assert.match(key.apiKey, /^smry_live_/);

    // Authenticated request succeeds
    const authedLibRes = await fetch(`${baseUrl}/api/v1/library`, {
      headers: { Authorization: `Bearer ${key.apiKey}` }
    });
    assert.equal(authedLibRes.status, 200);

    // Revoke key
    const revokeRes = await fetch(`${baseUrl}/api/v1/keys/${key.id}`, { method: "DELETE" });
    assert.equal(revokeRes.status, 200);

    // Request with revoked key is rejected with 401
    const rejectedRes = await fetch(`${baseUrl}/api/v1/library`, {
      headers: { Authorization: `Bearer ${key.apiKey}` }
    });
    assert.equal(rejectedRes.status, 401);
  } finally {
    await close();
  }
});
