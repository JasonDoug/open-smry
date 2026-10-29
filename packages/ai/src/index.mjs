import {
  AI_MODELS,
  SUMMARY_MODES,
  TTS_VOICES,
  chunkArticleIntoPassages,
  findExactPassages,
  tokenizeForSearch
} from "@summary-ai/shared";

/**
 * Resolves the requested model ID or provider shorthand ("claude", "gpt", "gemini")
 * to its full model descriptor.
 */
export function resolveModelDescriptor(modelOrProvider = "claude-3-7-sonnet") {
  const key = String(modelOrProvider || "claude-3-7-sonnet").toLowerCase().trim();
  const byId = AI_MODELS.find((m) => m.id.toLowerCase() === key);
  if (byId) return byId;
  const byProvider = AI_MODELS.find((m) => m.provider.toLowerCase() === key);
  return byProvider || AI_MODELS[0];
}

/**
 * Ranks sentences in an article by TF-IDF centrality and position to power
 * deterministic extractive summaries when no external API key is configured.
 */
export function rankArticleSentences(textContent = "", topN = 5) {
  const sentences = String(textContent || "")
    .replace(/\n+/g, " ")
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length >= 25);

  if (sentences.length === 0) {
    const fallback = String(textContent || "").trim();
    return fallback ? [fallback] : [];
  }

  const freqMap = new Map();
  for (const s of sentences) {
    for (const tok of tokenizeForSearch(s)) {
      freqMap.set(tok, (freqMap.get(tok) || 0) + 1);
    }
  }

  const scored = sentences.map((sentence, idx) => {
    const tokens = tokenizeForSearch(sentence);
    let score = 0;
    for (const tok of tokens) {
      score += freqMap.get(tok) || 1;
    }
    if (tokens.length > 0) {
      score = score / Math.pow(tokens.length, 0.65);
    }
    // Position bias: opening thesis and concluding sentences carry higher weight
    if (idx === 0) score *= 1.35;
    else if (idx === 1) score *= 1.15;
    else if (idx === sentences.length - 1) score *= 1.1;

    return { sentence, idx, score };
  });

  return scored
    .sort((a, b) => b.score - a.score)
    .slice(0, topN)
    .sort((a, b) => a.idx - b.idx)
    .map((item) => item.sentence);
}

/**
 * Calls configured external LLM provider (Claude, GPT, Gemini) if API keys are set,
 * otherwise returns null so the local extractive synthesis engine handles it seamlessly.
 */
async function callExternalLlmIfConfigured({
  modelDescriptor,
  systemPrompt,
  userPrompt,
  env = process.env,
  fetchImpl = globalThis.fetch
}) {
  if (typeof fetchImpl !== "function") return null;

  try {
    if (modelDescriptor.provider === "claude" && env.ANTHROPIC_API_KEY) {
      const res = await fetchImpl("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": env.ANTHROPIC_API_KEY,
          "anthropic-version": "2023-06-01"
        },
        body: JSON.stringify({
          model: env.DEFAULT_CLAUDE_MODEL || "claude-3-7-sonnet-latest",
          max_tokens: 1024,
          system: systemPrompt,
          messages: [{ role: "user", content: userPrompt }]
        })
      });
      if (res.ok) {
        const data = await res.json();
        return data?.content?.[0]?.text || null;
      }
    }

    if (modelDescriptor.provider === "gpt" && env.OPENAI_API_KEY) {
      const res = await fetchImpl("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          Authorization: `Bearer ${env.OPENAI_API_KEY}`
        },
        body: JSON.stringify({
          model: env.DEFAULT_GPT_MODEL || "gpt-4o",
          messages: [
            { role: "system", content: systemPrompt },
            { role: "user", content: userPrompt }
          ]
        })
      });
      if (res.ok) {
        const data = await res.json();
        return data?.choices?.[0]?.message?.content || null;
      }
    }

    if (modelDescriptor.provider === "gemini" && env.GEMINI_API_KEY) {
      const modelName = env.DEFAULT_GEMINI_MODEL || "gemini-2.5-pro";
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${env.GEMINI_API_KEY}`;
      const res = await fetchImpl(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: systemPrompt }] },
          contents: [{ role: "user", parts: [{ text: userPrompt }] }]
        })
      });
      if (res.ok) {
        const data = await res.json();
        return data?.candidates?.[0]?.content?.parts?.[0]?.text || null;
      }
    }
  } catch {
    return null;
  }
  return null;
}

/**
 * Generates customizable AI summaries:
 * - "tldr": Concise 2-3 sentence executive synthesis
 * - "bullets": Scannable bullet points
 * - "takeaways": Key takeaways & implications
 * - "executive": Structured deep research brief
 * - "custom": Driven by custom user prompt
 */
export async function generateSummary(
  article,
  {
    mode = "bullets",
    model = "claude-3-7-sonnet",
    customPrompt = "",
    env = process.env,
    fetchImpl = globalThis.fetch
  } = {}
) {
  const modelDesc = resolveModelDescriptor(model);
  const validMode = SUMMARY_MODES.find((m) => m.id === mode) ? mode : "bullets";
  const title = article?.title || "Untitled Article";
  const textContent = String(article?.textContent || "").trim();
  const passages = Array.isArray(article?.passages) && article.passages.length > 0
    ? article.passages
    : chunkArticleIntoPassages(article || {});

  const systemPrompt = `You are Summary AI (${modelDesc.name}), a rigorous research and reading assistant. Ground every statement in the provided article text.`;
  const userPrompt = customPrompt
    ? `Article: "${title}"\n\nCustom Instruction: ${customPrompt}\n\nText:\n${textContent.slice(0, 18000)}`
    : `Article: "${title}"\nSummarize in mode "${validMode}".\n\nText:\n${textContent.slice(0, 18000)}`;

  const externalText = await callExternalLlmIfConfigured({
    modelDescriptor: modelDesc,
    systemPrompt,
    userPrompt,
    env,
    fetchImpl
  });

  const topSentences = rankArticleSentences(textContent, 5);
  const topPassages = customPrompt
    ? findExactPassages([article], customPrompt, 3)
    : passages.slice(0, 3);

  let content = externalText;
  if (!content) {
    if (validMode === "tldr") {
      content = `**TL;DR (${modelDesc.name}):** ${topSentences.slice(0, 2).join(" ")}`;
    } else if (validMode === "bullets") {
      content = [
        `### Concise Bullet Summary — *${title}*`,
        ...topSentences.map((s) => `- ${s}`)
      ].join("\n");
    } else if (validMode === "takeaways") {
      content = [
        `### Key Takeaways — *${title}*`,
        ...topSentences.map((s, idx) => `${idx + 1}. **Takeaway #${idx + 1}:** ${s}`)
      ].join("\n");
    } else if (validMode === "executive") {
      content = [
        `### Executive Research Brief — *${title}*`,
        `**Core Thesis:** ${topSentences[0] || article?.excerpt || title}`,
        "",
        "**Supporting Evidence & Findings:**",
        ...topSentences.slice(1).map((s) => `- ${s}`),
        "",
        `**Scope:** ${article?.wordCount || 0} words (~${article?.readingTimeMinutes || 1} min read) via \`${article?.sourceUsed || "direct"}\`.`
      ].join("\n");
    } else {
      // Custom prompt mode
      const matchedQuotes = topPassages.map((p) => `- "${p.text}" *(Paragraph ${p.paragraphIndex + 1})*`);
      content = [
        `### Custom Prompt Synthesis (${modelDesc.name})`,
        `**Prompt:** *${customPrompt || "Analyze key themes"}*`,
        "",
        topSentences.slice(0, 3).join(" "),
        "",
        "**Direct Evidence from Text:**",
        ...matchedQuotes
      ].join("\n");
    }
  }

  return {
    model: modelDesc.id,
    modelName: modelDesc.name,
    provider: modelDesc.provider,
    mode: validMode,
    customPrompt: customPrompt || null,
    content,
    keyPoints: topSentences,
    citations: topPassages.map((p) => ({
      passageId: p.id,
      paragraphIndex: p.paragraphIndex,
      startOffset: p.startOffset,
      endOffset: p.endOffset,
      quote: p.text
    })),
    createdAt: new Date().toISOString()
  };
}

/**
 * Contextual "Ask AI": Highlight any specific passage to trigger targeted AI analysis,
 * definitions, critiques, or explanations of just that excerpt.
 */
export async function contextualAskAi({
  article,
  selectionText,
  action = "explain", // "explain" | "define" | "summarize" | "critique" | "custom"
  question = "",
  model = "claude-3-7-sonnet",
  env = process.env,
  fetchImpl = globalThis.fetch
}) {
  const modelDesc = resolveModelDescriptor(model);
  const excerpt = String(selectionText || "").trim();
  if (!excerpt) {
    throw new Error("selectionText is required for Contextual Ask AI.");
  }

  const relatedPassages = article
    ? findExactPassages([article], `${excerpt} ${question}`, 2)
    : [];

  const promptDirective =
    question ||
    (action === "define"
      ? "Define key terms and technical concepts in this passage."
      : action === "critique"
      ? "Analyze the assumptions, strengths, and potential limitations of this claim."
      : action === "summarize"
      ? "Condense this passage into a single crystal-clear sentence."
      : "Explain this passage clearly in the context of the broader article.");

  const externalAnswer = await callExternalLlmIfConfigured({
    modelDescriptor: modelDesc,
    systemPrompt: `You are ${modelDesc.name}. Provide a concise, insightful response focused on the highlighted excerpt.`,
    userPrompt: `Article Title: ${article?.title || "Current Reading"}\nHighlighted Excerpt: "${excerpt}"\nTask: ${promptDirective}`,
    env,
    fetchImpl
  });

  let answer = externalAnswer;
  if (!answer) {
    const terms = tokenizeForSearch(excerpt).slice(0, 5);
    if (action === "define") {
      answer = `**Contextual Definition (${modelDesc.name}):** In *"${excerpt.slice(0, 120)}${excerpt.length > 120 ? "..." : ""}"*, the key concepts (${terms.join(", ") || "highlighted terms"}) refer to how the author frames the primary mechanism in **${article?.title || "this article"}**. ${relatedPassages[0] ? `Supporting context from Paragraph ${relatedPassages[0].paragraphIndex + 1}: "${relatedPassages[0].text}"` : ""}`;
    } else if (action === "critique") {
      answer = `**Critical Analysis (${modelDesc.name}):** The highlighted passage asserts: *"${excerpt}"*. When evaluating this claim within **${article?.title || "the text"}**, verify the empirical scope and boundary conditions noted in Paragraph ${(relatedPassages[0]?.paragraphIndex ?? 0) + 1}.`;
    } else if (action === "summarize") {
      answer = `**Core Point (${modelDesc.name}):** ${excerpt.split(/(?<=[.!?])\s+/)[0] || excerpt}`;
    } else {
      answer = `**Contextual Explanation (${modelDesc.name}):** ${promptDirective}\n\nThe passage *"${excerpt}"* connects directly to the article's central argument${relatedPassages[0] ? ` (see Paragraph ${relatedPassages[0].paragraphIndex + 1}: "${relatedPassages[0].text}")` : "."}`;
    }
  }

  return {
    model: modelDesc.id,
    modelName: modelDesc.name,
    provider: modelDesc.provider,
    action,
    selectionText: excerpt,
    question: promptDirective,
    answer,
    relatedPassages: relatedPassages.map((p) => ({
      passageId: p.id,
      paragraphIndex: p.paragraphIndex,
      startOffset: p.startOffset,
      endOffset: p.endOffset,
      quote: p.text
    })),
    createdAt: new Date().toISOString()
  };
}

/**
 * Generates an answer grounded in one or more articles/library items with exact passage citations
 * (character startOffset, endOffset, paragraphIndex, and verbatim quote).
 */
export async function askLibraryWithCitations({
  articles = [],
  question = "",
  model = "claude-3-7-sonnet",
  topK = 3,
  env = process.env,
  fetchImpl = globalThis.fetch
}) {
  const modelDesc = resolveModelDescriptor(model);
  const topPassages = findExactPassages(articles, question, topK);

  const contextBlock = topPassages
    .map(
      (p, idx) =>
        `[Citation #${idx + 1} | ${p.articleTitle} | Paragraph ${p.paragraphIndex + 1} | Offsets ${p.startOffset}-${p.endOffset}]\n"${p.text}"`
    )
    .join("\n\n");

  const externalAnswer = await callExternalLlmIfConfigured({
    modelDescriptor: modelDesc,
    systemPrompt: `You are Summary AI (${modelDesc.name}). Answer the user's question using ONLY the provided passages and cite exact quotes.`,
    userPrompt: `Question: ${question}\n\nRetrieved Passages:\n${contextBlock}`,
    env,
    fetchImpl
  });

  let answer = externalAnswer;
  if (!answer) {
    if (topPassages.length === 0) {
      answer = "No matching passages were found in the loaded library for that question.";
    } else {
      const primary = topPassages[0];
      const secondary = topPassages[1];
      const lines = [
        `Based on **${primary.articleTitle}** (Paragraph ${primary.paragraphIndex + 1}, chars ${primary.startOffset}–${primary.endOffset}):`,
        "",
        `> "${primary.text}"`
      ];
      if (secondary && secondary.id !== primary.id) {
        lines.push(
          "",
          `Additional supporting passage from **${secondary.articleTitle}** (Paragraph ${secondary.paragraphIndex + 1}, chars ${secondary.startOffset}–${secondary.endOffset}):`,
          `> "${secondary.text}"`
        );
      }
      answer = lines.join("\n");
    }
  }

  return {
    question,
    model: modelDesc.id,
    modelName: modelDesc.name,
    provider: modelDesc.provider,
    answer,
    citations: topPassages.map((p) => ({
      passageId: p.id,
      articleId: p.articleId,
      articleTitle: p.articleTitle,
      articleUrl: p.articleUrl,
      paragraphIndex: p.paragraphIndex,
      startOffset: p.startOffset,
      endOffset: p.endOffset,
      quote: p.text,
      score: p.score
    })),
    createdAt: new Date().toISOString()
  };
}

/**
 * Interactive Streaming AI Chat:
 * Yields real-time word-by-word tokens followed by exact passage citations and completion event.
 */
export async function* streamChatResponse({
  article,
  messages = [],
  model = "claude-3-7-sonnet",
  env = process.env,
  fetchImpl = globalThis.fetch
}) {
  const lastUserMsg =
    [...messages].reverse().find((m) => m.role === "user")?.content ||
    "Summarize the core thesis of this article.";

  const ragResult = await askLibraryWithCitations({
    articles: article ? [article] : [],
    question: lastUserMsg,
    model,
    topK: 3,
    env,
    fetchImpl
  });

  const words = ragResult.answer.split(/(\s+)/).filter((w) => w.length > 0);
  let accumulated = "";

  for (const token of words) {
    accumulated += token;
    yield {
      type: "token",
      token,
      model: ragResult.model
    };
  }

  yield {
    type: "citations",
    citations: ragResult.citations
  };

  yield {
    type: "done",
    fullText: accumulated,
    model: ragResult.model,
    modelName: ragResult.modelName,
    citations: ragResult.citations
  };
}

/**
 * Karaoke-Style Highlighting & Natural Voice Engine:
 * Builds a deterministic word-by-word timestamp map (`startMs`, `endMs`, `charStart`, `charEnd`)
 * for any article, voice profile (10 distinct voices/accents), and playback speed (0.5x - 2.0x).
 */
export function buildKaraokeWordTimeline(
  textContent = "",
  {
    voiceId = "aria-us-f",
    speed = 1.0,
    baseWordsPerMinute = 165
  } = {}
) {
  const voice = TTS_VOICES.find((v) => v.id === voiceId) || TTS_VOICES[0];
  const clampedSpeed = Math.min(Math.max(Number(speed) || 1.0, 0.5), 2.0);
  const effectiveWpm = baseWordsPerMinute * (voice.rateMultiplier || 1.0) * clampedSpeed;
  const msPerAverageWord = 60000 / effectiveWpm;

  const fullText = String(textContent || "");
  const words = [];
  const wordRegex = /\S+/g;
  let match;
  let currentMs = 0;
  let wordIndex = 0;

  // Track paragraph boundaries
  const paragraphBreaks = [];
  const paraRegex = /\n\s*\n/g;
  let pMatch;
  while ((pMatch = paraRegex.exec(fullText)) !== null) {
    paragraphBreaks.push(pMatch.index);
  }

  while ((match = wordRegex.exec(fullText)) !== null) {
    const wordText = match[0];
    const charStart = match.index;
    const charEnd = charStart + wordText.length;

    // Determine paragraph index
    let paragraphIndex = 0;
    for (const brk of paragraphBreaks) {
      if (charStart > brk) paragraphIndex += 1;
      else break;
    }

    // Weight word duration by character length and trailing punctuation pauses
    const lengthFactor = Math.max(0.65, Math.min(wordText.length / 5.2, 2.1));
    const punctuationPauseMs = /[.!?]["']?$/.test(wordText)
      ? 240 / clampedSpeed
      : /[,;:—]["']?$/.test(wordText)
      ? 110 / clampedSpeed
      : 0;

    const durationMs = Math.round(msPerAverageWord * lengthFactor + punctuationPauseMs);
    const startMs = currentMs;
    const endMs = startMs + durationMs;
    currentMs = endMs;

    words.push({
      index: wordIndex,
      word: wordText,
      charStart,
      charEnd,
      paragraphIndex,
      startMs,
      endMs
    });
    wordIndex += 1;
  }

  return {
    voice,
    speed: clampedSpeed,
    totalDurationMs: currentMs,
    totalWords: words.length,
    words
  };
}

/**
 * Finds the active word at a given playback timestamp in milliseconds.
 */
export function findWordAtTimestamp(timeline, timestampMs = 0) {
  const list = timeline?.words || [];
  if (list.length === 0) return null;
  const t = Math.max(0, Number(timestampMs) || 0);

  let low = 0;
  let high = list.length - 1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    const item = list[mid];
    if (t >= item.startMs && t <= item.endMs) {
      return item;
    }
    if (t < item.startMs) {
      high = mid - 1;
    } else {
      low = mid + 1;
    }
  }
  return list[Math.min(low, list.length - 1)];
}
