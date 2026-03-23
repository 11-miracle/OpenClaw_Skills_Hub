# IMAP Query Cheat Sheet

Use this sheet when combining `--search` with structured filters.

## Raw IMAP Search Examples

Unread in inbox:

```text
UNSEEN
```

From a sender:

```text
FROM "billing@example.com"
```

Subject contains keyword:

```text
SUBJECT "invoice"
```

Date range:

```text
SINCE "01-Mar-2026" BEFORE "01-Apr-2026"
```

Logical OR:

```text
OR FROM "boss@example.com" FROM "ceo@example.com"
```

## Common CLI Patterns

Unread + latest 20:

```bash
"$SKILL_DIR/scripts/read_imap.sh" --unseen --limit 20 --output table
```

Date + sender + body preview:

```bash
"$SKILL_DIR/scripts/read_imap.sh" \
  --since 2026-03-01 \
  --from "billing@example.com" \
  --include-body \
  --max-body-chars 400 \
  --output json
```

Custom raw search:

```bash
"$SKILL_DIR/scripts/read_imap.sh" \
  --search 'OR FROM "boss@example.com" SUBJECT "urgent"' \
  --limit 30 \
  --output table
```

## Notes

- `--search` takes IMAP syntax (`DD-Mon-YYYY` dates).
- `--since` and `--before` take `YYYY-MM-DD` and are converted automatically.
- If both `--search` and structured flags are used, criteria are combined.
