/**
 * Summary AI Browser Extension Background Worker
 * Compatible with Chromium (Chrome, Edge, Opera), Firefox, and Safari WebExtensions.
 */

export const DEFAULT_SERVER_URL = "http://localhost:3333";

export function buildReaderRedirectUrl(targetUrl, serverUrl = DEFAULT_SERVER_URL) {
  const base = String(serverUrl || DEFAULT_SERVER_URL).replace(/\/+$/, "");
  return `${base}/?url=${encodeURIComponent(targetUrl)}`;
}

export async function quickSaveAndSummarizeTab({
  tabUrl,
  tabTitle = "",
  rawHtml = null,
  model = "claude-3-7-sonnet",
  summaryMode = "tldr",
  serverUrl = DEFAULT_SERVER_URL,
  fetchImpl = globalThis.fetch
}) {
  const base = String(serverUrl || DEFAULT_SERVER_URL).replace(/\/+$/, "");
  const res = await fetchImpl(`${base}/api/v1/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: tabUrl,
      title: tabTitle || undefined,
      rawHtml,
      model,
      summaryMode,
      tags: ["browser-extension"]
    })
  });
  if (!res.ok) {
    throw new Error(`Extension API request failed: HTTP ${res.status}`);
  }
  return await res.json();
}

// Register browser context menus when running inside WebExtension runtime
const browserApi = globalThis.chrome || globalThis.browser;
if (browserApi?.runtime?.onInstalled && browserApi?.contextMenus) {
  browserApi.runtime.onInstalled.addListener(() => {
    browserApi.contextMenus.create({
      id: "summary-ai-open-reader",
      title: "Open Page in Summary AI Reader",
      contexts: ["page", "link"]
    });
    browserApi.contextMenus.create({
      id: "summary-ai-ask-selection",
      title: "Ask Summary AI about Selection",
      contexts: ["selection"]
    });
  });
}
