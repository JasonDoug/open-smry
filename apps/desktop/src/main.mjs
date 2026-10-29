import { createApiServer } from "@summary-ai/api";
import { SummaryStore } from "@summary-ai/api/store";
import { SummaryMcpServer } from "@summary-ai/mcp-server";

/**
 * Summary AI Desktop Runtime Controller (Electron / Tauri Hybrid Shell)
 * Launches the embedded local REST API + Web Reader server and embeds an in-process
 * Model Context Protocol (MCP) daemon for local desktop AI agents.
 */
export class DesktopAppController {
  constructor({ port = 0, dataFile = null } = {}) {
    this.port = port;
    this.store = new SummaryStore({ dataFile });
    this.api = createApiServer({ store: this.store });
    this.mcp = new SummaryMcpServer({ store: this.store });
    this.activePort = null;
  }

  async start() {
    await new Promise((resolve) => {
      this.api.server.listen(this.port, "127.0.0.1", resolve);
    });
    const addr = this.api.server.address();
    this.activePort = addr.port;
    return {
      readerUrl: `http://127.0.0.1:${this.activePort}`,
      openApiUrl: `http://127.0.0.1:${this.activePort}/openapi.json`,
      windowConfig: {
        title: "Summary AI — Desktop Reader & Research Studio",
        width: 1380,
        height: 880,
        globalShortcuts: ["CommandOrControl+Shift+S", "CommandOrControl+Shift+L"]
      }
    };
  }

  async stop() {
    if (this.api?.server?.listening) {
      await new Promise((resolve) => this.api.server.close(resolve));
    }
  }
}
