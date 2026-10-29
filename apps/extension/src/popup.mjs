import { buildReaderRedirectUrl, quickSaveAndSummarizeTab } from "./background.mjs";

export async function handlePopupSummarizeClick({
  tabUrl,
  tabTitle,
  model = "claude-3-7-sonnet",
  serverUrl = "http://localhost:3333",
  fetchImpl = globalThis.fetch
}) {
  const result = await quickSaveAndSummarizeTab({
    tabUrl,
    tabTitle,
    model,
    summaryMode: "tldr",
    serverUrl,
    fetchImpl
  });
  return {
    readerUrl: buildReaderRedirectUrl(tabUrl, serverUrl),
    summaryText: result.summary?.content || "",
    articleId: result.article?.id
  };
}
