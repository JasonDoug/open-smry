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
