<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:3d023727c3b2ebc21cce708de88af60518df508bab8d6ea6f54df7a12d7e7dc2 -->

# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Security Practices

* **API Keys**: Agent and script API keys (`smry_live_...`) are stored as SHA-256 hashes at rest; raw tokens are returned only once upon creation and can be revoked immediately.
* **HTML Sanitization**: All extracted third-party web pages are strictly sanitized to strip `<script>`, `<iframe>`, inline event handlers (`onload`, `onerror`), and tracking pixels before rendering in Reader Mode.
* **SSRF Protection**: The extraction engine validates URL schemes (`http:` / `https:`) and blocks private/loopback network ranges in production mode.

## Reporting a Vulnerability

Please report security vulnerabilities privately via GitHub Security Advisories rather than opening a public issue.

## Anonymous session credentials

Reader session IDs are bearer secrets. Keep them private like API keys; do not share session URLs or include IDs in logs, analytics, or public examples. New sessions use 192 random bits. Possession of a session ID authorizes access to its settings and persisted provider keys. Legacy short IDs cannot authorize persisted provider keys in agent requests; create a new session and save the keys again, or supply per-request keys.


<!-- /coderabbit-ai-generated:v1 -->