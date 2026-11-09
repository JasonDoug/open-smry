/**
 * Summary AI — Web Reader Application Server (Port 3333).
 * Serves the Distraction-Free Web Reader UI and seamlessly proxies
 * /api/*, /docs, /redoc, and /openapi.json to the Python FastAPI backend.
 */
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { pipeline } from "node:stream";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PUBLIC_DIR = path.join(__dirname, "public");

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".ttf": "font/ttf"
};

export function createWebServer(options = {}) {
  const backendUrl = options.backendUrl || process.env.BACKEND_URL || "http://127.0.0.1:8001";
  const parsedBackend = new URL(backendUrl);

  const server = http.createServer((req, res) => {
    // Parse against a constant base: the Host header is client-controlled and
    // must never influence URL resolution. Reject malformed request targets.
    let parsedReqUrl;
    try {
      parsedReqUrl = new URL(req.url, "http://localhost");
    } catch {
      res.writeHead(400, { "Content-Type": "text/plain" });
      res.end("400 Bad Request");
      return;
    }
    const pathname = parsedReqUrl.pathname;

    // 1. Proxy API, OpenAPI & Docs requests to the FastAPI backend
    if (
      pathname.startsWith("/api/") ||
      pathname === "/docs" ||
      pathname.startsWith("/docs/") ||
      pathname === "/redoc" ||
      pathname.startsWith("/redoc/") ||
      pathname === "/openapi.json"
    ) {
      const proxyReq = http.request(
        {
          hostname: parsedBackend.hostname,
          port: parsedBackend.port || 80,
          path: req.url,
          method: req.method,
          headers: {
            ...req.headers,
            host: parsedBackend.host,
            "x-forwarded-host": req.headers.host || "localhost:3333",
            "x-forwarded-proto": "http"
          }
        },
        (proxyRes) => {
          res.writeHead(proxyRes.statusCode || 200, proxyRes.headers);
          // pipeline propagates upstream failures instead of hanging the client;
          // on success the pipeline completes without touching the streams.
          pipeline(proxyRes, res, (err) => {
            if (err) {
              proxyRes.destroy();
              res.destroy();
            }
          });
        }
      );

      proxyReq.on("error", (err) => {
        if (!res.headersSent) {
          res.writeHead(502, { "Content-Type": "application/json" });
          res.end(
            JSON.stringify({
              error: "Backend Service Unavailable",
              detail: `Could not reach Python FastAPI backend at ${backendUrl}. Ensure 'npm run dev:api' is running.`,
              code: err.code
            })
          );
        } else {
          res.destroy();
        }
      });

      // Propagate client-side disconnects to the backend request; on normal
      // completion (request body fully sent) the response is still pending.
      pipeline(req, proxyReq, (err) => {
        if (err) proxyReq.destroy();
      });
      return;
    }

    // 2. Static file serving for the Web Reader UI
    let relativeFile = pathname === "/" ? "index.html" : pathname.replace(/^\/+/, "");
    // Prevent directory traversal
    const safePath = path.normalize(relativeFile).replace(/^(\.\.[\/\\])+/, "");
    const filePath = path.join(PUBLIC_DIR, safePath);

    fs.stat(filePath, (err, stats) => {
      if (err || !stats.isFile()) {
        // Fallback to index.html for SPA-style client routing if not found
        const fallbackPath = path.join(PUBLIC_DIR, "index.html");
        fs.readFile(fallbackPath, (fallbackErr, content) => {
          if (fallbackErr) {
            res.writeHead(404, { "Content-Type": "text/plain" });
            res.end("404 Not Found");
            return;
          }
          res.writeHead(200, { "Content-Type": MIME_TYPES[".html"] });
          res.end(content);
        });
        return;
      }

      const ext = path.extname(filePath).toLowerCase();
      const contentType = MIME_TYPES[ext] || "application/octet-stream";
      res.writeHead(200, { "Content-Type": contentType });
      fs.createReadStream(filePath).pipe(res);
    });
  });

  return { server, backendUrl };
}

// Self-executing runner when executed via `node apps/web/server.mjs`
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const PORT = parseInt(process.env.PORT || "3333", 10);
  const { server, backendUrl } = createWebServer();
  server.listen(PORT, "0.0.0.0", () => {
    console.log(`\n⚡ Summary AI Web Reader UI running at: http://localhost:${PORT}`);
    console.log(`🔗 Proxying API & OpenAPI requests to: ${backendUrl}\n`);
  });
}
