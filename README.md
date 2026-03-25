# OpenClaw Skills Hub

面向 Claude Code 的技能插件集合，开箱即用。每个技能封装完整的工具链（脚本 + AI提示词 + 参考文档），通过 SKILL.md 描述符驱动，无需额外配置即可在 Claude Code 会话中调用。

---

## 技能列表

### 🔍 amazon-insights — 亚马逊商品洞察分析

从 ASIN 到可视化报告的全流程分析工具。支持三种模式：

| 模式 | 触发方式 | 输出 |
|------|---------|------|
| **单品分析** | 提供 1 个 ASIN | 单品 HTML 洞察报告 |
| **批量分析** | 提供 2-9 个 ASIN | 多份单品报告 + 汇总总览 |
| **品类总览** | 提供 10+ ASIN / Excel 文件 / 说"品类分析" | 含 9 部分的品类级 HTML 报告 |

方法论框架：`PSPS` · `$APPEALS（8维）` · `KANO（5类）` · `ABSA方面级情感` · `痛爽痒矩阵` · `用户旅程地图`

---

### 📨 imap-read-email — IMAP 邮件读取

通过 IMAP 协议读取、筛选、汇总邮件。

- 支持 Gmail、Outlook、163、QQ 等主流邮箱
- 按发件人 / 主题 / 日期灵活过滤
- 触发词：「收邮件」「查邮箱」「未读邮件」「邮件汇总」
- 依赖：`python3`，环境变量 `IMAP_PASSWORD`

---

### 📧 smtp-send-email — SMTP 邮件发送

通过 SMTP 协议发送邮件与附件。

- 支持抄送、密送、群发、HTML 正文、附件
- 适配 163 邮箱及其他标准 SMTP 服务商
- 触发词：「发邮件」「发附件」「发送报告」「send email」
- 依赖：`python3`，环境变量 `SMTP_USER`、`SMTP_PASSWORD`

---

## 技能目录结构

```
<skill-name>/
├── SKILL.md              # 技能描述符（触发条件、工作流、AI 提示词入口）
├── scripts/              # 可执行脚本（Shell / Python）
├── references/           # 参考文档（配置说明、API速查、报告规范等）
└── assets/               # 静态资源（可选）
```

## 使用方式

1. 将仓库克隆到本地：
   ```bash
   git clone https://gitee.com/miracle_1101/openclaw_skills_hub.git ~/openclaw/skills
   ```

2. 在 Claude Code 的配置中注册 skills 目录（参考 OpenClaw 文档）。

3. 在会话中直接用自然语言触发，例如：
   - `帮我分析亚马逊 B08N5LNQCX`
   - `查一下我的未读邮件`
   - `发一封报告给 xx@example.com`

## 参与贡献

1. Fork 本仓库
2. 新建分支 `feat/skill-name`
3. 按照现有技能结构添加 `SKILL.md` + 脚本
4. 提交 Pull Request

## License

[MIT](LICENSE)
