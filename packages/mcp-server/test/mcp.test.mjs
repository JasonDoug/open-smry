import test from "node:test";
import assert from "node:assert/strict";
import { SummaryMcpServer } from "../src/index.mjs";
import { SummaryStore } from "@summary-ai/api/store";

test("Sprint 7: MCP Server exposes tools and resources for external AI agents", async () => {
  const store = new SummaryStore();
  const mcp = new SummaryMcpServer({ store });

  // 1. initialize
  const initRes = await mcp.handleJsonRpc({
    jsonrpc: "2.0",
    id: 1,
    method: "initialize"
  });
  assert.equal(initRes.result.serverInfo.name, "summary-ai-mcp");

  // 2. tools/list
  const toolsRes = await mcp.handleJsonRpc({
    jsonrpc: "2.0",
    id: 2,
    method: "tools/list"
  });
  assert.ok(toolsRes.result.tools.some((t) => t.name === "save_and_summarize"));
  assert.ok(toolsRes.result.tools.some((t) => t.name === "ask_library"));

  // 3. Call save_and_summarize tool
  const saveRes = await mcp.handleJsonRpc({
    jsonrpc: "2.0",
    id: 3,
    method: "tools/call",
    params: {
      name: "save_and_summarize",
      arguments: {
        url: "https://science.example.com/fusion-ignition",
        title: "Net Energy Gain in Inertial Fusion",
        textContent: [
          "Inertial confinement fusion uses 192 ultraviolet laser beams focused onto a gold hohlraum.",
          "The target capsule produced 3.15 megajoules of fusion energy output from 2.05 megajoules of laser input."
        ].join("\n\n"),
        model: "claude-3-7-sonnet",
        summaryMode: "tldr"
      }
    }
  });
  const savedPayload = JSON.parse(saveRes.result.content[0].text);
  assert.equal(savedPayload.title, "Net Energy Gain in Inertial Fusion");

  // 4. Call ask_library tool to verify exact passage citation
  const askRes = await mcp.handleJsonRpc({
    jsonrpc: "2.0",
    id: 4,
    method: "tools/call",
    params: {
      name: "ask_library",
      arguments: {
        question: "How many megajoules of fusion energy output did the target capsule produce?"
      }
    }
  });
  const askPayload = JSON.parse(askRes.result.content[0].text);
  assert.ok(askPayload.citations.length >= 1);
  assert.match(askPayload.citations[0].quote, /3\.15 megajoules of fusion energy output/);
});
