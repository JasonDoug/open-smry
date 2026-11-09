import fs from "node:fs";
import path from "node:path";

const REQUIRED_PATHS = [
  "README.md",
  "LICENSE",
  "CONTRIBUTING.md",
  "CODE_OF_CONDUCT.md",
  "SECURITY.md",
  ".env.example",
  "docs/ROADMAP.md",
  "docs/BUG_TRACKER.md",
  ".github/workflows/ci.yml",
  "packages/shared/src/index.mjs",
  "backend/pyproject.toml",
  "backend/app/config.py",
  "backend/app/db/models.py",
  "backend/app/db/session.py",
  "backend/app/schemas/domain.py",
  "backend/app/api/v1/router.py",
  "backend/app/api/v1/extraction_router.py",
  "backend/app/extraction/sanitizer.py",
  "backend/app/extraction/racer.py",
  "backend/app/extraction/youtube.py",
  "backend/app/extraction/books.py",
  "backend/app/rag/embeddings.py",
  "backend/app/rag/retriever.py",
  "backend/app/agents/llm_router.py",
  "backend/app/agents/state.py",
  "backend/app/agents/summarizer.py",
  "backend/app/agents/qa_critic.py",
  "backend/app/agents/context_analyst.py",
  "backend/app/agents/graph.py",
  "backend/app/api/v1/library_router.py",
  "backend/app/api/v1/agents_router.py",
  "backend/app/main.py",
  "backend/tests/test_sprint1_foundation.py",
  "backend/tests/test_sprint2_extraction.py",
  "backend/tests/test_sprint3_rag_library.py",
  "backend/tests/test_sprint4_langgraph_agents.py",
  "apps/web/package.json",
  "apps/web/server.mjs",
  "apps/web/public/index.html",
  "apps/web/public/styles.css",
  "apps/web/public/app.js",
  "apps/web/test/web.test.mjs"
];

let missing = 0;
for (const rel of REQUIRED_PATHS) {
  const full = path.resolve(process.cwd(), rel);
  if (!fs.existsSync(full)) {
    console.error(`Missing required repository file: ${rel}`);
    missing += 1;
  }
}

if (missing > 0) {
  process.exit(1);
}
console.log(`✔ Verified ${REQUIRED_PATHS.length} required repository architecture & OSS governance files.`);
