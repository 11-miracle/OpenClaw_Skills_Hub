# OpenClaw Skills Hub

A collection of plug-and-play skills for Claude Code. Each skill is driven by a `SKILL.md` descriptor and bundles scripts, prompts, and references so it can be invoked directly with natural language.

[中文说明](README.md)

## Quick Start

1. Clone this repository:

```bash
git clone https://gitee.com/miracle_1101/openclaw_skills_hub.git ~/openclaw/skills
```

2. Register `~/openclaw/skills` in your Claude Code skills configuration.
3. Trigger skills in chat, for example:
   - `Analyze Amazon product B08N5LNQCX`
   - `Check my unread emails`
   - `Send the report to xx@example.com`

## Requirements

- Common: `python3`, `bash`, `curl`
- `imap-read-email`: `IMAP_PASSWORD`
- `smtp-send-email`: `SMTP_USER`, `SMTP_PASSWORD`
- `apify`: `APIFY_TOKEN` (required when using Apify actors)

## Skill Index

| Skill | Purpose | Typical Triggers |
|---|---|---|
| `amazon-insights` | Amazon product/category intelligence with HTML reports | `analyze amazon <ASIN>`, `category analysis` |
| `imap-read-email` | Read, filter, and summarize IMAP emails | `check unread emails`, `summarize emails` |
| `smtp-send-email` | Send emails and attachments via SMTP | `send email`, `send report` |
| `apify` | Run Apify actors for scraping and data extraction | `run apify actor`, `scrape with apify` |

## Featured Skills

### `amazon-insights`

End-to-end analysis from ASIN to visual report. Three modes:

| Mode | Trigger | Output |
|---|---|---|
| Single product | 1 ASIN | Single-product HTML report |
| Batch | 2–9 ASINs | Per-product reports + summary |
| Category overview | 10+ ASINs / Excel file / "category analysis" | 9-section category-level HTML report |

Frameworks: `PSPS`, `$APPEALS (8 dimensions)`, `KANO (5 categories)`, `ABSA`, `Pain–Delight–Itch matrix`, `User journey map`.

### `imap-read-email`

Read, filter, and summarize emails via IMAP.

- Supports Gmail, Outlook, 163, QQ, and other standard IMAP providers
- Flexible filtering by sender, subject, or date
 
### `smtp-send-email`

Send emails and attachments via SMTP.

- Supports CC, BCC, bulk send, HTML body, and file attachments
- Works with 163 Mail and any standard SMTP provider
 
### `apify`

- Run any Apify actor via REST API
- Fetch dataset items, key-value outputs, and run logs

## Skill Structure

```text
<skill-name>/
├── SKILL.md
├── scripts/
├── references/
└── assets/   # optional
```

## Contributing

1. Fork the repository
2. Create a branch: `feat/<skill-name>`
3. Add `SKILL.md` and scripts following the existing structure
4. Submit a Pull Request

## License

[Apache License 2.0](LICENSE)
