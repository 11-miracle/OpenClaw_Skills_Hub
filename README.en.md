# OpenClaw Skills Hub

A collection of plug-and-play skills for Claude Code. Each skill bundles a complete toolchain — scripts, AI prompts, and reference docs — driven by a `SKILL.md` descriptor and invokable through natural language in any Claude Code session.

---

## Skills

### 🔍 amazon-insights — Amazon Product Intelligence

End-to-end analysis pipeline from ASIN to visual HTML report. Three modes:

| Mode | Trigger | Output |
|------|---------|--------|
| **Single product** | 1 ASIN | Single-product HTML insight report |
| **Batch** | 2–9 ASINs | Per-product reports + batch summary |
| **Category overview** | 10+ ASINs / Excel file / "category analysis" | 9-section category-level HTML report |

Analytical frameworks: `PSPS` · `$APPEALS (8 dimensions)` · `KANO (5 categories)` · `ABSA aspect-level sentiment` · `Pain–Delight–Itch matrix` · `User journey map`

---

### 📨 imap-read-email — IMAP Email Reader

Read, filter, and summarize emails via IMAP.

- Supports Gmail, Outlook, 163, QQ, and other standard IMAP providers
- Flexible filtering by sender, subject, or date
- Trigger phrases: "check inbox", "unread emails", "summarize emails"
- Requires: `python3`, env var `IMAP_PASSWORD`

---

### 📧 smtp-send-email — SMTP Email Sender

Send emails and attachments via SMTP.

- Supports CC, BCC, bulk send, HTML body, and file attachments
- Works with 163 Mail and any standard SMTP provider
- Trigger phrases: "send email", "send attachment", "email report"
- Requires: `python3`, env vars `SMTP_USER` and `SMTP_PASSWORD`

---

## Skill Directory Structure

```
<skill-name>/
├── SKILL.md              # Skill descriptor (triggers, workflow, AI prompt entry points)
├── scripts/              # Executable scripts (Shell / Python)
├── references/           # Reference docs (config notes, API cheatsheets, report specs)
└── assets/               # Static assets (optional)
```

## Getting Started

1. Clone the repository:
   ```bash
   git clone https://gitee.com/miracle_1101/openclaw_skills_hub.git ~/openclaw/skills
   ```

2. Register the skills directory in your Claude Code configuration (see OpenClaw docs).

3. Invoke skills using natural language in your session, for example:
   - `Analyze Amazon product B08N5LNQCX`
   - `Check my unread emails`
   - `Send the report to xx@example.com`

## Contributing

1. Fork the repository
2. Create a branch: `feat/skill-name`
3. Add `SKILL.md` + scripts following the existing skill structure
4. Submit a Pull Request

## License

[MIT](LICENSE)
