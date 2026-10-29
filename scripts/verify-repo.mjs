import fs from "node:fs";
import path from "node:path";

const REQUIRED_PATHS = [
  "README.md",
  "LICENSE",
  "CONTRIBUTING.md",
  "CODE_OF_CONDUCT.md",
  "SECURITY.md",
  "docs/ROADMAP.md",
  ".github/workflows/ci.yml",
  "packages/shared/src/index.mjs",
  "packages/extractor/src/index.mjs",
  "packages/ai/src/index.mjs",
  "packages/mcp-server/src/index.mjs",
  "apps/api/src/app.mjs",
  "apps/web/public/index.html",
  "apps/desktop/src/main.mjs",
  "apps/mobile/src/MobileReaderController.mjs",
  "apps/extension/manifest.json",
  "apps/extension/manifest.firefox.json"
];

let missing = 0;
for (const rel of REQUIRED_PATHS) {
  const full = path.resolve(process.cwd(), rel);
  if (!fs.existsSync(full)) {
    console.error(`Missing required project file: ${rel}`);
    missing += 1;
  }
}

if (missing > 0) {
  process.exit(1);
}
console.log(`✔ Verified ${REQUIRED_PATHS.length} core repository files across packages and apps.`);
