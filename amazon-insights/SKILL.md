---
name: amazon-insights
description: 亚马逊商品洞察分析。当用户说"帮我收集亚马逊中的 [ASIN]"、"分析亚马逊商品 [ASIN]"、"爬取 [ASIN] 的评论"、"查一下亚马逊 [ASIN]"、"选品分析 [ASIN]"、"帮我拆解竞品 [ASIN]"、"批量分析 [多个ASIN]"等时触发。支持多站点（默认美国站）、批量队列。通过直接爬取获取商品基础信息，浏览器自动化+Apify多级降级爬取差评（100-1000条，不足自动切站），6个专家AI分析后输出：聊天框流式报告 + 标准化HTML可视化报告 + 批量汇总总览，按ASIN存档。
---

# Amazon Insights Skill

## 分析专家角色总览

详细提示词见 `references/analysis-prompts.md`。
方法论框架：**PSPS 模型 · $APPEALS（8维）· KANO（5类+量化）· 用户旅程地图 · ABSA方面级情感分析 · 痛爽痒矩阵**

| 角色 | 输入 | 输出 | 时机 |
|---|---|---|---|
| ① 商品图视觉分析 | 详情图URL(前5张) | 视觉审计报告 + 战略解码 | 拿到图片后，与②并行 |
| ② 需求分析师(VOC) | 差评原文(已翻译) | PSPS+ABSA+$APPEALS(8维)+KANO(5类)+痛爽痒 结构化JSON | 评论到手后立即执行 |
| ③ 单品拆解专家 | 商品数据+②结论 | must_copy/must_avoid/conclusion | ①完成后执行 |
| ④ 竞品可视化拆解 | 图片+①②结论 | 视觉战术文字报告 | ①②均完成后 |
| ⑤ 市场分析师 | 多竞品数据 | 市场机会报告 | 多ASIN或明确要求时 |
| ⑥ 产品企划总监 | 前面所有结论 | 产品定义+视觉企划 | 选品建议/产品优化时 |
| ⑦ 用户旅程分析师 | 评论数据+②结论 | 6阶段旅程摩擦热力图+峰终洞察 JSON | ②完成后触发 |

**单 ASIN 默认执行**：① + ② + ③ + ④ + ⑦
**多 ASIN / 批量**：额外执行 ⑤
**选品建议**：额外执行 ⑥

---

## 评论采集规范（强制执行）

| 参数 | 规则 |
|------|------|
| 星级 | 3星及以下（critical） |
| 最少数量 | **100条**（硬门槛） |
| 上限 | **1000条** |
| 默认目标 | 200条（用户未指定时） |
| 不足处理 | 自动切换站点，全部失败则报告中输出说明 |
| 说明模板 | ⚠️ ASIN {X} 在所有已尝试站点（US/UK/DE/JP）差评不足100条，实际获取 N 条，分析结果仅供参考。可能原因：商品评论数量较少 / 近期刚上架 / 该站点无此商品。 |

---

## 工作流

### Step 1：解析输入

从用户输入提取：
- **ASIN**：10位字母数字，支持多个（逗号/空格/换行分隔）
- **站点**：参考 `references/domain-map.md`，默认 `amazon.com`
- **评论数**：用户指定则用指定值，否则默认 `200`；上限 1000
- **模式**：单品分析 / 批量分析 / 市场分析 / 选品建议

**批量模式判断**：用户提供 2+ ASIN 或说"批量"→ 写入 `~/.openclaw/workspace/batch/queue.txt`，运行 `batch-run.sh`

---

### Step 2：并行采集（线程A + 线程B 同时启动）

```bash
bash ~/openclaw/skills/amazon-insights/scripts/run-pipeline.sh <ASIN> <domain> <max_reviews>
```

---

**线程A：商品基础信息**

```bash
bash ~/openclaw/skills/amazon-insights/scripts/scrape-product.sh <ASIN> <domain>
```

完成后：
- 立即流式输出商品卡片到聊天框
- 触发 ① 图片视觉分析 + ③ 单品拆解（并行）

---

**线程B：评论爬取（三级降级链 + 自动站点切换）**

```
Level 1: Apify（90s 硬超时）
    ↓ 0条 / 超时 / 失败
Level 2: 浏览器自动化翻页
    ├─ 登录检测 → 已登录直接翻页 / 未登录提示用户
    ├─ 翻页循环：while 已采集 < 目标数 and hasNext:
    │       提取当前页评论（仅 rating ≤ 3 的条目）
    │       点击 next page
    └─ 采集结果 < 100 → 触发自动站点切换
Level 3: 自动站点切换（无需用户选择）
    切换顺序: amazon.com → amazon.co.uk → amazon.de → amazon.co.jp
    每个站点重走 Level 1 → Level 2
    各站结果合并去重（按 title+body 前50字）
    全部站点合计 ≥ 100 → 成功
    全部站点合计 < 100 → 标注说明，继续分析
```

**Level 2 翻页循环（严格执行）：**

```javascript
// 执行 JS 提取当前页评论
() => {
  const reviews = [];
  document.querySelectorAll('[data-hook="review"]').forEach(el => {
    const ratingRaw = el.querySelector('[data-hook="review-star-rating"] .a-icon-alt')?.textContent || '';
    const ratingNum = parseFloat(ratingRaw.split(' ')[0]) || 0;
    if (ratingNum <= 3 && ratingNum > 0) {
      reviews.push({
        rating: ratingNum,
        title:  el.querySelector('[data-hook="review-title"] span:not(.a-icon-alt)')?.textContent?.trim() || '',
        body:   el.querySelector('[data-hook="review-body"] span')?.textContent?.trim() || '',
        date:   el.querySelector('[data-hook="review-date"]')?.textContent?.trim() || '',
        verified: !!el.querySelector('[data-hook="avp-badge"]')
      });
    }
  });
  const nextBtn = document.querySelector('li.a-last:not(.a-disabled) a');
  return JSON.stringify({ reviews, hasNext: !!nextBtn });
}
```

循环条件：`hasNext == true AND 已采集 < max_reviews AND 页数 < 100`

完成后将结果写入：`$REPORT_DIR/<ASIN>-reviews-raw.json`
同时写入元数据：`$REPORT_DIR/<ASIN>-reviews-meta.json`

```json
{
  "total": 150,
  "domains_tried": ["amazon.com", "amazon.co.uk"],
  "domains_success": {"amazon.com": 80, "amazon.co.uk": 70},
  "reached_minimum": true,
  "method": "browser",
  "note": ""
}
```

---

### Step 3：分析层（流式推送）

> **流式原则：每个专家分析完立即输出一段到聊天框，不等全部完成**

#### ① 商品图视觉分析（线程A完成后触发）
- 读取 `references/analysis-prompts.md` → 第1节
- 输入：aplus_images 前5张（不足补 images）
- 输出：`image_analysis` 文本字段
- **完成后立即推送视觉摘要到聊天框**

#### ② 需求分析师 VOC（线程B完成后立即触发）
- 读取 `references/analysis-prompts.md` → 第3节
- 非中文评论先翻译（第7节，50条/批）
- **注意：3星评论完整保留（含正面内容），供爽点/痒点提取使用**
- 输出结构化 JSON 写入 `data.json`：
  - `psps`（用户画像+场景+Top3痛点+机会Gap）
  - `absa`（方面级情感分析+危机预警项）
  - `keywords` / `appeals`（8维）/ `kano`（5类+量化）
  - `pain_pleasure_itch`（痛爽痒三维图谱+营销文案建议）
  - `opportunity` / `radar_expect` / `radar_actual` / `sample_reviews`（带category分类）
- **完成后立即推送 VOC 摘要到聊天框**（含 PSPS 画像 + 痛爽痒强度）

#### ③ 单品拆解专家（①完成后触发）
- 读取 `references/analysis-prompts.md` → 第4节
- 输出写入 `data.json`：teardown.must_copy / teardown.must_avoid / teardown.conclusion / teardown.identity_tag
- **完成后立即推送拆解结论到聊天框**

#### ④ 竞品可视化拆解（①②均完成后触发）
- 读取 `references/analysis-prompts.md` → 第5节
- 输出：文字报告嵌入最终 HTML

#### ⑦ 用户旅程分析师（②完成后触发，与③④并行）
- 读取 `references/analysis-prompts.md` → 第8节
- 输入：评论数据 + ②的 VOC 结论摘要
- 输出结构化 JSON 写入 `data.json`：
  - `journey_map`（6阶段旅程数据，含摩擦分/触点/情绪/痛点/机会）
  - `top3_friction_stages`（最高摩擦阶段Top3）
  - `peak_end_insight`（峰终定律洞察）
  - `journey_optimization_actions`（3条可执行改善建议）
- **完成后立即推送旅程摩擦热力图摘要到聊天框**

---

### Step 4：整合数据

组装 `$REPORT_DIR/<ASIN>-data.json`：

```json
{
  "product": { ...基础信息... },
  "reviews_meta": {
    "total": 150,
    "domains_tried": ["amazon.com"],
    "domains_success": {"amazon.com": 150},
    "reached_minimum": true,
    "method": "browser",
    "note": ""
  },
  "image_analysis": "...",
  "reviews_analysis": {
    "psps": {
      "persona": {"age_range":"...", "purchase_role":"...", "expertise_level":"...", "price_sensitivity":"...", "motivation":"..."},
      "scenario": {"time":"...", "space":"...", "trigger_buy":"...", "trigger_complaint":"..."},
      "top3_pain_points": [{"rank":1, "pain":"...", "kano_type":"Must-be", "quote":"..."}],
      "solution_gap": "电梯演讲式机会描述"
    },
    "absa": {
      "aspects": [{"aspect":"...", "positive_pct":30, "negative_pct":60, "neutral_pct":10, "intensity":8.5, "crisis_flag":true, "top_negative_quote":"..."}],
      "crisis_items": ["紧急改善项"]
    },
    "keywords": [{"word":"...", "count":0}],
    "appeals": {"Price":0, "Availability":0, "Packaging":0, "Performance":0, "Ease":0, "Assurances":0, "LifeCycle":0, "Social":0},
    "kano": {
      "must_be":    [{"feature":"...", "frequency":0, "severity":"critical", "opportunity_score":0, "evolution_note":"..."}],
      "performance":[{"feature":"...", "frequency":0, "opportunity_score":0, "evolution_note":"..."}],
      "attractive": [{"feature":"...", "frequency":0, "opportunity_score":0, "evolution_note":"..."}],
      "indifferent":[{"feature":"...", "frequency":0}],
      "reverse":    [{"feature":"...", "frequency":0, "note":"..."}]
    },
    "pain_pleasure_itch": {
      "pain":    {"score":0, "items":[{"description":"...", "quote":"...", "frequency":0}], "copywriting_suggestion":"..."},
      "pleasure":{"score":0, "items":[{"description":"...", "quote":"...", "frequency":0}], "copywriting_suggestion":"..."},
      "itch":    {"score":0, "items":[{"description":"...", "quote":"...", "frequency":0}], "copywriting_suggestion":"..."}
    },
    "opportunity": "...",
    "radar_expect": [8,8,8,8,8,8],
    "radar_actual":  [5,5,5,5,5,5],
    "sample_reviews": [{"stars":1, "title":"...", "body":"...", "category":"pain/pleasure/itch"}]
  },
  "journey_analysis": {
    "journey_map": [
      {"stage_id":1, "stage_name":"认知/搜索阶段", "friction_score":0, "touchpoints":[], "user_emotion":"...", "pain_points":[], "opportunities":[], "peak_or_end":false}
    ],
    "top3_friction_stages": [{"stage_name":"...", "friction_score":0, "key_fix":"..."}],
    "peak_end_insight": "...",
    "journey_optimization_actions": ["..."]
  },
  "teardown": {
    "identity_tag": "[普通竞品]",
    "must_copy": ["..."],
    "must_avoid": ["..."],
    "conclusion": "..."
  }
}
```

---

### Step 5：生成报告（标准7模块）

```bash
python3 ~/openclaw/skills/amazon-insights/scripts/generate-report.py \
  <ASIN>-product.json \
  <ASIN>-report.html \
  <ASIN>-data.json
```

**报告固定结构（不可缺省）：**
1. Header（ASIN + 站点 + 生成时间 + 身份标签）
2. 基础信息（标题/价格/评分/五点/主图）
3. 详情图 & 视觉分析
4. 差评分析（采集说明 + 关键词 + APPEALS玫瑰图 + KANO表格 + 雷达图 + 机会点）
5. 单品拆解（Must Copy / Must Avoid / 结论）
6. 差评原声剧场（最多9条）
7. Footer

**视觉规范：**
- 背景：`#f5f5f5`（页面）/ `#ffffff`（卡片）
- 主色：`#2c3e50` / 警示色：`#b71c1c` / 机会色：`#1b5e20`
- 卡片：`border:1px solid #e0e0e0`，无圆角，无阴影
- 字体：`-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- 图表：ECharts，玫瑰图($APPEALS) + 雷达图(满意度鸿沟)

---

### Step 5B：流式聊天框输出顺序

```
T+30s  → 商品卡片（标题/价格/评分）
T+50s  → 视觉分析摘要（①完成后）
T+60s  → 单品拆解结论（③完成后）
T+90s  → VOC差评摘要（②完成后）：含 PSPS 用户画像 + 痛爽痒强度 + ABSA危机预警
T+110s → 旅程摩擦热力图摘要（⑦完成后）：最高摩擦阶段 + 峰终洞察
T+150s → 最终报告路径 + Canvas展示
```

---

### Step 6：批量模式

**触发**：用户提供 2+ ASIN 或说"批量"

```bash
# 写入队列
echo "B07Y5GHJSX" >> ~/.openclaw/workspace/batch/queue.txt

# 启动批量
bash ~/openclaw/skills/amazon-insights/scripts/batch-run.sh

# 查看进度
bash ~/openclaw/skills/amazon-insights/scripts/batch-status.sh

# 生成汇总报告
python3 ~/openclaw/skills/amazon-insights/scripts/generate-batch-summary.py
```

**汇总报告**：`~/.openclaw/workspace/reports/batch-summary.html`
- 总进度条 + KPI（总数/完成/分析中/失败）
- ASIN 明细表格（图片/名称/评分/差评数/机会点/报告链接）
- 每60秒自动刷新

---

## 错误处理

| 情况 | 处理 |
|------|------|
| 商品爬取失败 | 降级用 browser 工具抓取，标注来源 |
| 所有站点评论 < 100 | 在报告第4模块顶部输出⚠️说明，继续分析 |
| Apify token 耗尽 | 静默切 Level 2，不中断流程 |
| 评论 < 20 条 | 标注"差评极少，分析仅供参考"，继续执行 |
| HTML 报告 < 50KB | 视为生成失败，重新执行 generate-report.py |
| 批量某个 ASIN 失败 | 记录 failed 状态，跳过继续下一个 |

---

## 存档结构

```
~/.openclaw/workspace/
├── batch/
│   ├── queue.txt              ← 待处理 ASIN 队列
│   ├── status.json            ← 批量状态机
│   └── batch-*.log            ← 执行日志
└── reports/
    ├── batch-summary.html     ← 批量汇总总览
    └── <ASIN>/
        ├── <ASIN>-product.json      ← 商品基础信息
        ├── <ASIN>-reviews-raw.json  ← 原始评论数据
        ├── <ASIN>-reviews-meta.json ← 评论采集元数据
        ├── <ASIN>-data.json         ← 完整分析数据
        └── <ASIN>-report.html       ← 标准化HTML报告
```

---

## 参考文件

- `references/analysis-prompts.md` — 6个专家角色完整提示词
- `references/domain-map.md` — 站点映射 + 降级链配置
- `references/report-spec.md` — 报告规范文档
- `scripts/scrape-product.sh` — 商品信息爬取
- `scripts/apify-reviews.sh` — Apify Level 1 评论爬取
- `scripts/browser-reviews.py` — Level 2 浏览器自动化指令生成
- `scripts/run-pipeline.sh` — 并行调度主脚本
- `scripts/generate-report.py` — 标准报告生成（7模块）
- `scripts/batch-run.sh` — 批量队列调度
- `scripts/batch-status.sh` — 批量进度查看
- `scripts/generate-batch-summary.py` — 汇总总览生成
