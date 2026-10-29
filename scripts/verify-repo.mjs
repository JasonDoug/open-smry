import fs from "node:fs";
import path from "node:path";

const SPRINT1_REQUIRED_PATHS = [
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
  "backend/app/main.py",
  "backend/tests/test_sprint1_foundation.py",
  "backend/tests/test_sprint2_extraction.py"
];

let missing = 0;
for (const rel of SPRINT1_REQUIRED_PATHS) {
  const full = path.resolve(process.cwd(), rel);
  if (!fs.existsSync(full)) {
    console.error(`Missing required Sprint 1 file: ${rel}`);
    missing += 1;
  }
}

if (missing > 0) {
  process.exit(1);
}
console.log(`✔ Verified ${SPRINT1_REQUIRED_PATHS.length} Sprint 1 polyglot architecture & OSS governance files.`);
