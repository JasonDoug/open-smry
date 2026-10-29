import test from "node:test";
import assert from "node:assert/strict";
import { DesktopAppController } from "../src/main.mjs";

test("Sprint 8 (Desktop): DesktopAppController starts embedded local Reader API and MCP daemon", async () => {
  const desktop = new DesktopAppController({ port: 0 });
  const info = await desktop.start();
  try {
    assert.match(info.readerUrl, /^http:\/\/127\.0\.0\.1:\d+$/);
    const metaRes = await fetch(`${info.readerUrl}/api/v1/meta`);
    assert.equal(metaRes.status, 200);
    const meta = await metaRes.json();
    assert.equal(meta.readerFonts.length, 7);

    // Verify embedded MCP daemon works over shared desktop store
    const mcpTools = await desktop.mcp.handleJsonRpc({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/list"
    });
    assert.ok(mcpTools.result.tools.length >= 6);
  } finally {
    await desktop.stop();
  }
});
