---
name: imap-read-email
description: 通过 IMAP 读取、筛选、汇总邮件。用户提到“收邮件”“查邮箱”“未读邮件”“邮件汇总”“IMAP inbox”，或需要按发件人/主题/日期过滤邮件时触发。适用于 Gmail、Outlook、163、QQ 等 IMAP 邮箱。
homepage: https://docs.python.org/3/library/imaplib.html
metadata:
  {
    "openclaw":
      {
        "emoji": "📨",
        "primaryEnv": "IMAP_PASSWORD",
        "requires": { "anyBins": ["python3", "python"] },
      },
  }
---

# IMAP Read Email (OpenClaw)

## 能力

- 从 IMAP 邮箱读取邮件（默认只读）
- 按未读、日期、发件人、主题过滤
- 输出 `json` 或 `table`
- 可选提取正文预览用于汇总

## OpenClaw 适配约定

统一使用绝对路径，避免当前工作目录变化导致命令失败：

```bash
SKILL_DIR="$HOME/.openclaw/skills/imap-read-email"
"$SKILL_DIR/scripts/read_imap.sh" --help
```

## 触发关键词

- 收邮件 / 查邮箱 / 邮件列表
- 未读邮件 / 最近邮件 / 今日邮件
- 按发件人筛选邮件 / 按主题筛选邮件
- 邮件汇总 / 邮件整理
- imap inbox / unread emails / email triage

## 环境变量

标准变量（优先）：

- `IMAP_HOST`
- `IMAP_PORT` (可选，默认 `993`)
- `IMAP_USERNAME`
- `IMAP_PASSWORD`
- `IMAP_MAILBOX` (可选，默认 `INBOX`)

兼容 OpenClaw 前缀变量（作为别名）：

- `OPENCLAW_IMAP_HOST`
- `OPENCLAW_IMAP_PORT`
- `OPENCLAW_IMAP_USERNAME`
- `OPENCLAW_IMAP_PASSWORD`
- `OPENCLAW_IMAP_MAILBOX`

Gmail 示例：

```bash
export IMAP_HOST="imap.gmail.com"
export IMAP_USERNAME="you@example.com"
export IMAP_PASSWORD="your_app_password"
```

## 常用命令

先定义路径：

```bash
SKILL_DIR="$HOME/.openclaw/skills/imap-read-email"
```

拉取未读邮件（表格）：

```bash
"$SKILL_DIR/scripts/read_imap.sh" \
  --unseen \
  --limit 20 \
  --output table
```

拉取账单主题邮件（JSON + 正文摘要）：

```bash
"$SKILL_DIR/scripts/read_imap.sh" \
  --since 2026-03-01 \
  --from "billing@example.com" \
  --subject "invoice" \
  --include-body \
  --max-body-chars 600 \
  --output json
```

163/126/yeah 邮箱（需要 ID 时）：

```bash
"$SKILL_DIR/scripts/read_imap.sh" \
  --host "imap.163.com" \
  --username "you@163.com" \
  --unseen \
  --id-mode always \
  --output table
```

## 执行规范

1. 默认保持只读，不要启用 `--read-write`，除非用户明确要求改动邮件状态。
2. 优先使用小范围查询（`--since` + `--limit`）避免拉取过量邮件。
3. 用户要求“直接查一下邮件”时，直接执行命令，不只给命令模板。
4. 汇总时优先输出：发件人、主题、时间、是否需要行动。

## 常见错误

- Authentication failed:
  - 使用邮箱授权码（app password），不要用网页登录密码。
  - 确认已开启 IMAP 和相关安全设置（通常需要 2FA）。
- Empty results:
  - 放宽筛选条件，或去掉 `--unseen`。
  - 检查邮箱文件夹名（`INBOX`、`Archive`、服务商本地化目录）。
- TLS or certificate errors:
  - 检查主机和端口。
  - `--insecure` 仅用于临时排障，不要长期使用。

## References（按需读取）

- Provider notes: [references/imap-provider-notes.md](references/imap-provider-notes.md)
- Search cheat sheet: [references/imap-query-cheatsheet.md](references/imap-query-cheatsheet.md)
- CLI help: `"$SKILL_DIR/scripts/read_imap.sh" --help`
