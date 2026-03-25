# OpenClaw Skills Hub

面向 Claude Code 的技能插件集合。每个技能均采用 `SKILL.md` 描述符驱动，并配套脚本、提示词与参考文档，支持在会话中通过自然语言直接触发。

[English README](README.en.md)

## 快速开始

1. 克隆仓库到本地：

```bash
git clone https://gitee.com/miracle_1101/openclaw_skills_hub.git ~/openclaw/skills
```

2. 在 Claude Code 配置中注册 `~/openclaw/skills` 目录。
3. 在会话中直接触发技能，例如：
   - `帮我分析亚马逊 B08N5LNQCX`
   - `查一下我的未读邮件`
   - `发一封报告给 xx@example.com`

## 运行依赖

- 通用：`python3`、`bash`、`curl`
- `imap-read-email`：`IMAP_PASSWORD`
- `smtp-send-email`：`SMTP_USER`、`SMTP_PASSWORD`
- `apify`：`APIFY_TOKEN`（可选，使用 Apify Actor 时需要）

## 技能总览

| 技能 | 用途 | 典型触发词 |
|---|---|---|
| `amazon-insights` | 亚马逊单品/批量/品类洞察，输出可视化 HTML 报告 | `分析亚马逊 <ASIN>`、`品类分析` |
| `imap-read-email` | IMAP 邮件读取、筛选与汇总 | `查未读邮件`、`邮件汇总` |
| `smtp-send-email` | SMTP 邮件发送与附件投递 | `发邮件`、`发送报告` |
| `apify` | 调用 Apify Actors 进行抓取与数据提取 | `用 apify 抓取...`、`run apify actor` |

## 重点技能说明

### `amazon-insights`

从 ASIN 到可视化洞察报告的全流程分析，支持三种模式：

| 模式 | 触发方式 | 输出 |
|---|---|---|
| 单品分析 | 1 个 ASIN | 单品 HTML 洞察报告 |
| 批量分析 | 2-9 个 ASIN | 多份单品报告 + 汇总总览 |
| 品类总览 | 10+ ASIN / Excel 文件 / “品类分析” | 9 部分品类级 HTML 报告 |

分析框架：`PSPS`、`$APPEALS(8维)`、`KANO(5类)`、`ABSA`、`痛爽痒矩阵`、`用户旅程地图`。

### `imap-read-email`

- 支持 Gmail、Outlook、163、QQ 等主流 IMAP 邮箱
- 支持按发件人/主题/日期过滤

### `smtp-send-email`

- 支持抄送、密送、群发、HTML 正文与附件
- 适配 163 邮箱及标准 SMTP 服务商

### `apify`

- 通过 Apify REST API 运行 Actor 并获取结果
- 支持查询 Actor、运行任务、轮询状态、读取 Dataset 与日志

## 目录结构

```text
<skill-name>/
├── SKILL.md
├── scripts/
├── references/
└── assets/   # optional
```

## 贡献方式

1. Fork 本仓库
2. 新建分支 `feat/<skill-name>`
3. 按现有结构新增 `SKILL.md` 与脚本
4. 提交 Pull Request

## License

[Apache License 2.0](LICENSE)
