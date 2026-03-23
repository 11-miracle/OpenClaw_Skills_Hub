# IMAP Provider Notes

## Common Hosts

| Provider | IMAP Host | Port | Notes |
|---|---|---:|---|
| Gmail | `imap.gmail.com` | 993 | Enable IMAP and use app password |
| Outlook / Microsoft 365 | `outlook.office365.com` | 993 | Modern auth policies may apply |
| Yahoo | `imap.mail.yahoo.com` | 993 | Use app password |
| iCloud | `imap.mail.me.com` | 993 | App-specific password required |

## Authentication Tips

- Prefer app passwords when the provider supports them.
- If 2FA is enabled, normal account password may fail for IMAP.
- Some enterprise tenants disable basic IMAP auth entirely.

## IMAP Search Notes

- `ALL`: all messages in selected mailbox
- `UNSEEN`: unread messages only
- `SINCE <date>`: on or after date
- `BEFORE <date>`: before date
- `FROM "foo@bar.com"`: sender filter
- `SUBJECT "invoice"`: subject filter

Date format expected by IMAP: `DD-Mon-YYYY` (for example: `23-Mar-2026`).
The helper script accepts `YYYY-MM-DD` and converts automatically.

## Folder Names

- Default mailbox is usually `INBOX`.
- Archives/spam/sent folder names vary by provider and locale.
- If a folder is not found, list folders manually via IMAP client tools and retry.
