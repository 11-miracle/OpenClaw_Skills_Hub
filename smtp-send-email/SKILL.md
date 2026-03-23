---
name: smtp-send-email
description: 使用 SMTP 发送邮件与附件。用户提到“发邮件”“邮件”“发附件”“发送报告”“抄送”“密送”“群发”或 “send email / attachment / smtp” 时触发。适合 163 邮箱及其他 SMTP 服务商。
homepage: https://docs.python.org/3/library/smtplib.html
metadata:
  {
    "openclaw":
      {
        "emoji": "📧",
        "primaryEnv": "SMTP_PASSWORD",
        "requires":
          {
            "anyBins": ["python3", "python"],
            "env": ["SMTP_USER", "SMTP_PASSWORD"],
          },
      },
  }
---

# SMTP Send Email (OpenClaw)

## 能力

- 发送纯文本邮件
- 发送 HTML 邮件
- 添加一个或多个附件
- 支持收件人 / 抄送 / 密送
- 支持 SSL(465) 与 STARTTLS(587)

## OpenClaw 适配约定

使用绝对技能路径，避免因当前工作目录不同导致命令失败：

```bash
SKILL_DIR="$HOME/.openclaw/skills/smtp-send-email"
"$SKILL_DIR/scripts/send_smtp_email.sh" --help
```

## 触发关键词

- 发邮件
- 邮件
- 发附件 / 发送附件
- 邮件报告
- 抄送 / 密送 / 群发
- send email
- email attachment
- smtp mail

## 环境变量

优先读取标准变量：

- `SMTP_HOST` (默认 `smtp.163.com`)
- `SMTP_PORT` (默认 `465`)
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM` (可选)
- `SMTP_STARTTLS` (可选，`true/1/yes/on`)

兼容 OpenClaw 前缀变量（作为别名）：

- `OPENCLAW_SMTP_HOST`
- `OPENCLAW_SMTP_PORT`
- `OPENCLAW_SMTP_USER`
- `OPENCLAW_SMTP_PASSWORD`
- `OPENCLAW_SMTP_FROM`
- `OPENCLAW_SMTP_STARTTLS`

163 邮箱示例：

```bash
export SMTP_HOST="smtp.163.com"
export SMTP_PORT="465"
export SMTP_USER="your_163@163.com"
export SMTP_PASSWORD="your_app_password"
```

## 常用命令

先定义路径：

```bash
SKILL_DIR="$HOME/.openclaw/skills/smtp-send-email"
```

发送纯文本 + 附件：

```bash
"$SKILL_DIR/scripts/send_smtp_email.sh" \
  --to "someone@example.com" \
  --subject "文件已发送" \
  --body "你好，附件请查收。" \
  --attach "/absolute/path/report.pdf"
```

发送 HTML + 抄送 + 密送：

```bash
"$SKILL_DIR/scripts/send_smtp_email.sh" \
  --to "owner@example.com" \
  --cc "team@example.com" \
  --bcc "audit@example.com" \
  --subject "日报 HTML 版本" \
  --html \
  --body-file "/absolute/path/daily.html" \
  --attach "/absolute/path/daily.csv"
```

587 + STARTTLS：

```bash
"$SKILL_DIR/scripts/send_smtp_email.sh" \
  --smtp-port 587 \
  --no-ssl \
  --starttls \
  --to "someone@example.com" \
  --subject "STARTTLS 测试" \
  --body "hello"
```

仅检查参数（不实际发出）：

```bash
"$SKILL_DIR/scripts/send_smtp_email.sh" \
  --to "someone@example.com" \
  --subject "dry run" \
  --body "check" \
  --dry-run
```

## 执行规范

1. 发信前先确认附件路径存在（绝对路径）。
2. 未明确主题时，用文件名或任务名做主题。
3. 有附件时，正文说明“附件请查收”。
4. 若用户要求“立即发”，直接执行发送，不只给命令模板。

## 常见错误

1. `SMTP user is required`  
未设置 `SMTP_USER`（或 `OPENCLAW_SMTP_USER`）。

2. `SMTP password is required`  
未设置 `SMTP_PASSWORD`（或 `OPENCLAW_SMTP_PASSWORD`）。

3. `535 Authentication failed`  
通常用了登录密码而不是 SMTP 授权码/专属密码。

4. `Attachment not found`  
附件路径错误；改成绝对路径并检查文件是否存在。

更多 163 配置见 [references/smtp-163.md](references/smtp-163.md)。
