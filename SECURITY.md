# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do not open a public GitHub issue for security problems.**

Instead, email the maintainer at the address listed in the repository profile or open a private security advisory on GitHub.

Please include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fix (optional)

You can expect an initial response within 72 hours. We will keep you informed of the progress toward a fix and public disclosure.

## Security Practices in This Project

- All API keys, tokens and secrets are loaded exclusively from environment variables
- No secrets are committed to the repository
- Telegram bot only accepts commands from pre-authorized user IDs
- The system never publishes content to X automatically
- Dependencies are pinned with version ranges in `requirements.txt`
- The application runs as a non-root user when installed via the provided scripts

Thank you for helping keep the project and its users safe.
