import path from "node:path";
import { createApiServer } from "./app.mjs";
import { SummaryStore } from "./store.mjs";

const PORT = Number(process.env.PORT || 3333);
const HOST = process.env.HOST || "0.0.0.0";
const DATA_DIR = process.env.DATA_DIR || path.resolve(process.cwd(), ".data");

const store = new SummaryStore({
  dataFile: path.join(DATA_DIR, "summary-ai-store.json")
});

const { server } = createApiServer({ store });

server.listen(PORT, HOST, () => {
  console.log(`========================================================`);
  console.log(`  Summary AI — Reader, Summarizer & Agentic Research Hub`);
  console.log(`  Web Reader UI : http://localhost:${PORT}`);
  console.log(`  OpenAPI Docs  : http://localhost:${PORT}/docs`);
  console.log(`  OpenAPI Spec  : http://localhost:${PORT}/openapi.json`);
  console.log(`========================================================`);
});
