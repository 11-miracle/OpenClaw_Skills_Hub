---
name: amazon-insights
description: 亚马逊商品洞察分析。支持两种模式：①单品/批量分析——用户说"帮我收集/分析/爬取/查一下/选品/拆解竞品 [ASIN]"时触发，通过爬取+AI分析输出单品HTML报告；②品类总览报告——用户提供Excel离线数据文件、10+个ASIN、或说"品类分析/竞品总览/生成可视化报告"时触发，输出含9部分的品类级HTML洞察报告（含AI动态总结）。方法论：PSPS · $APPEALS(8维) · KANO(5类) · ABSA方面级情感 · 痛爽痒矩阵 · 用户旅程地图。
---

# Amazon Insights Skill

## 路径变量（跨平台，执行前必须先解析）

所有路径通过 `scripts/paths.py` 统一解析，**不硬编码任何绝对路径**：

```python
import sys, os
sys.path.insert(0, "{SKILL_SCRIPTS}")  # 由 AI 替换为实际 scripts/ 目录
from paths import get_paths, ensure_dirs
P = ensure_dirs("{ASIN}")   # 自动创建所有必要目录

# 之后使用：
# P["workspace"]  — OpenClaw 工作目录
# P["reports"]    — 报告根目录
# P["batch"]      — 批量任务目录
# P["memory"]     — 状态/记忆文件目录
# P["scripts"]    — skill scripts 目录
# P["report_dir"] — 当前 ASIN 报告目录
```

平台自动推导规则：
| 平台 | workspace 默认路径 |
|------|-------------------|
| Mac / Linux | `~/.openclaw/workspace` |
| Windows | `%APPDATA%\openclaw\workspace` |

自定义路径：设置环境变量 `OPENCLAW_WORKSPACE` / `OPENCLAW_SKILL_DIR` 覆盖默认值。

**bash 脚本中获取路径：**
```bash
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_PATHS=$(python3 "${SCRIPTS_DIR}/paths.py" "${ASIN}")
REPORT_DIR=$(echo "$_PATHS" | python3 -c "import json,sys; print(json.load(sys.stdin)['report_dir'])")
```

---

## 设计原则

- **AI 是分析师，不是 RPA**：AI 直接用 browser 工具抓数据、判断策略、灵活应对异常
- **脚本只做渲染**：固定脚本只负责把 AI 产出的结构化数据渲染成 HTML，不承担采集逻辑
- **写→验→修→继续**：AI 写任何代码都必须立即验证，有错自己修，不跳过不降级放弃
- **流式输出**：不等所有数据，拿到多少输出多少，用户实时看到进展

---

## 模式判断（入口）

| 输入 | 模式 |
|------|------|
| 1–9 个 ASIN | 单品/批量模式 → 执行 Phase 1–5 |
| 10+ 个 ASIN / Excel 文件 / "品类分析/竞品总览" | 品类总览模式 → 执行 Phase 6–7 |

---

## 单品 / 批量模式

### Phase 0：解析输入

从用户输入提取：
- **ASIN**：10位字母数字，多个用逗号/空格/换行分隔
- **站点**：见 `references/domain-map.md`，默认 `amazon.com`
- **意图**：

| 用户说 | intent |
|--------|--------|
| 快速看/扫一眼/简单看 | `quick` |
| 默认不说 | `standard` |
| 深度/详细/完整分析 | `deep` |
| 多 ASIN / 批量 | `batch` |

批量模式（2+ ASIN）：写入 `{P['batch']}/queue.txt`，串行处理每个 ASIN。

---

### Phase 1：采集商品信息（browser 工具直接执行）

**不走 scrape-product.sh**，AI 直接用 browser 工具：

```
1. browser open: https://www.{domain}/dp/{ASIN}
2. browser act: wait domcontentloaded
3. browser act: evaluate 提取结构化数据
```

提取 JS：
```javascript
() => {
  const title      = document.querySelector('#productTitle')?.textContent?.trim() || '';
  const price      = document.querySelector('.a-price-whole')?.textContent?.trim() || '';
  const rating     = document.querySelector('#acrPopover')?.getAttribute('title')?.match(/[\d.]+/)?.[0] || '';
  const reviewCount= document.querySelector('#acrCustomerReviewText')?.textContent?.trim() || '';
  const bullets    = Array.from(document.querySelectorAll('#feature-bullets .a-list-item'))
                       .map(e=>e.textContent.trim()).filter(t=>t.length>10).slice(0,5);
  const images     = Array.from(document.querySelectorAll('#altImages img'))
                       .map(i=>(i.dataset.oldHires||i.src).replace(/\._[A-Z0-9_,]+_\./,'._SL500_.'))
                       .filter(u=>u.includes('media-amazon')).slice(0,8);
  const apluses    = Array.from(document.querySelectorAll('#aplus img, #aplus_feature_div img'))
                       .map(i=>i.src).filter(u=>u.includes('media-amazon')).slice(0,5);
  return JSON.stringify({title,price,rating,reviewCount,bullets,images,apluses});
}
```

**拿到数据后立即输出商品卡片到聊天框**（不等评论）：
```
📦 {TITLE}
💰 ${PRICE}  ⭐ {RATING}（{REVIEW_COUNT} 条评论）
🔗 https://www.{domain}/dp/{ASIN}
```

遇到反爬/空数据：
- 刷新重试一次
- 仍失败 → 尝试 `amazon.co.uk` 同 ASIN
- 告知用户并继续后续流程（不卡死）

保存到：`{P["report_dir"]}/{ASIN}-product.json`

---

### Phase 2：评论采集策略决策

**AI 自己判断**，不走固定脚本流程：

**Step A：计算目标量**

从 Phase 1 拿到的 `reviewCount` 解析总评论数，套公式：

| 总评论数 | 基础目标 |
|---------|---------|
| < 200 | 全采（上限200） |
| 200–2000 | 20%，最少50条 |
| 2000–10000 | 10%，最少100条 |
| > 10000 | 5%，最少150，上限500 |

意图修正：quick×0.3 / standard×1.0 / deep×2.0 / batch×0.5
最终结果 clamp 到 [20, 1000]。

**Step B：选择采集方式（必须执行，不得跳过）**

**⚠️ 必须先执行以下命令，根据输出结果决定路径，不得凭印象判断：**

```bash
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "$HOME/openclaw/skills/amazon-insights/scripts")"
python3 - << 'EOF'
import json, os, time
state_file = os.path.expanduser("~/.openclaw/workspace/memory/apify-token-state.json")
d = json.load(open(state_file)) if os.path.exists(state_file) else {}
ex = d.get("exhausted_at", 0)
hrs = (time.time() - ex) / 3600
tokens = [v for k, v in sorted(os.environ.items()) if k.startswith("APIFY_TOKEN")]
print(f"STATUS={'cooldown' if hrs < 4 else 'available'}")
print(f"TOKENS={len(tokens)}")
print(f"COOLDOWN_HRS={hrs:.1f}")
EOF
```

输出 `STATUS=available` 且 `TOKENS>0` → **必须走 Apify 路径**
输出 `STATUS=cooldown` 或 `TOKENS=0` → 走浏览器翻页路径

| 状态 | 策略 |
|------|------|
| available + TOKENS>0 | **必须先用 Apify**（bash apify-reviews.sh），失败才切浏览器 |
| cooldown 或 TOKENS=0 | 跳过 Apify，直接浏览器翻页 |

---

### Phase 3：评论采集执行

**Apify 路径**（Step B 判定 available + TOKENS>0 时，必须首先执行）：

**Step C-1：差评采集（必须）**
```bash
bash {P["scripts"]}/apify-reviews.sh {ASIN} {domain} {target} negative
```
- 成功且 >= 20 条 → 保存 `{ASIN}-reviews-raw.json`，继续 Step C-2
- 返回 0 条（exit 2）→ 切浏览器路径（差评+好评均走浏览器），记录 `exhausted_at`
- 失败/超时（exit 1）→ 切浏览器路径，记录 `exhausted_at`

**Step C-2：好评采集（差评成功后紧接执行，不并行）**
```bash
bash {P["scripts"]}/apify-reviews.sh {ASIN} {domain} 25 positive
```
- 成功且 >= 5 条 → 保存 `{ASIN}-reviews-positive.json`，进 Phase 4
- 失败/0 条 → 走浏览器好评补采（见下方浏览器路径好评部分），不阻断 Phase 4
- 好评不足时：`reviews-positive.json` 写入 `{"data_unavailable": true, "reviews": []}`，Phase 4 标注"好评样本不足，结论供参考"

**❌ 禁止在未执行 Apify 差评的情况下直接走浏览器翻页路径。**

**浏览器翻页路径**：

**差评抓取**（1-3星）：

AI 直接用 browser 工具逐页抓取，URL 模板：
```
https://www.{domain}/product-reviews/{ASIN}?filterByStar=critical&sortBy=recent&pageNumber={n}
```

每页提取 JS：
```javascript
() => {
  const reviews = [];
  document.querySelectorAll('[data-hook="review"]').forEach(el => {
    const ratingEl  = el.querySelector('[data-hook="review-star-rating"] .a-icon-alt');
    const ratingNum = parseFloat((ratingEl?.textContent||'').split(' ')[0]) || 0;
    if (ratingNum > 0 && ratingNum <= 3) {
      reviews.push({
        rating:   ratingNum,
        title:    el.querySelector('[data-hook="review-title"] span:not(.a-icon-alt)')?.textContent?.trim() || '',
        body:     el.querySelector('[data-hook="review-body"] span')?.textContent?.trim() || '',
        date:     el.querySelector('[data-hook="review-date"]')?.textContent?.trim() || '',
        verified: !!el.querySelector('[data-hook="avp-badge"]')
      });
    }
  });
  const hasNext = !!document.querySelector('li.a-last:not(.a-disabled) a');
  return JSON.stringify({reviews, hasNext});
}
```

**硬出口（任意触发立即停止）**：
- ✅ 已采集 >= 目标数
- 🔄 连续3页无新数据
- ⛔ hasNext=false 且已采集 >= 20 条
- ⏰ 翻页超过15页（Amazon 通常最多允许10页）

不足20条时自动切换站点（顺序：.co.uk → .de → .co.jp），每站最多3页，切完就停，不再等待。

**每采集10条输出一次进度**：
```
📥 已采集 {n} 条差评，目标 {target} 条...
```

保存到：`{P["report_dir"]}/{ASIN}-reviews-raw.json`

---

**好评补采**（差评浏览器路径完成后，或 Apify 好评步骤失败时触发）：

URL 模板：
```
https://www.{domain}/product-reviews/{ASIN}?filterByStar=five_star&sortBy=recent&pageNumber={n}
```

每页提取 JS（与差评对称，仅星级过滤条件不同）：
```javascript
() => {
  const reviews = [];
  document.querySelectorAll('[data-hook="review"]').forEach(el => {
    const ratingEl  = el.querySelector('[data-hook="review-star-rating"] .a-icon-alt');
    const ratingNum = parseFloat((ratingEl?.textContent||'').split(' ')[0]) || 0;
    if (ratingNum >= 4) {   // 仅保留好评
      reviews.push({
        rating:   ratingNum,
        title:    el.querySelector('[data-hook="review-title"] span:not(.a-icon-alt)')?.textContent?.trim() || '',
        body:     el.querySelector('[data-hook="review-body"] span')?.textContent?.trim() || '',
        date:     el.querySelector('[data-hook="review-date"]')?.textContent?.trim() || '',
        verified: !!el.querySelector('[data-hook="avp-badge"]')
      });
    }
  });
  const hasNext = !!document.querySelector('li.a-last:not(.a-disabled) a');
  return JSON.stringify({reviews, hasNext});
}
```

**硬出口（好评只需少量样本，比差评更严格）**：
- ✅ 已采集 >= 25 条
- ⛔ hasNext=false
- ⏰ 翻页超过 2 页（好评不需要深翻）

好评 < 5 条时写入 `{"data_unavailable": true, "reviews": []}` 并标注，不影响后续分析。

保存到：`{P["report_dir"]}/{ASIN}-reviews-positive.json`

---

### Phase 4：AI 分析（流式输出）

评论够20条即可开始分析，不等满。

提示词在 `references/analysis-prompts.md`，按以下顺序并行执行：

**① 视觉分析**（Phase 1 完成后立即触发，不等评论）
- 输入：apluses 前5张图片
- 提示词：`references/analysis-prompts.md` 第1节
- 完成后立即输出视觉摘要

**② VOC 需求分析**（评论到手后触发）
- 非中文评论先翻译（`references/analysis-prompts.md` 第7节，50条/批）；差评池与好评池分别翻译
- 输入：全部差评（`reviews-raw.json`）+ 好评池（`reviews-positive.json`，若 `data_unavailable=true` 则跳过好评侧分析）
- 提示词：第3节（PSPS + ABSA + $APPEALS + KANO + 痛爽痒 + review_summary + innovation）
- 输出结构化 JSON 到内存

**③ 单品拆解**（①完成后触发）
- 提示词：第4节
- 完成后立即输出 Must Copy / Must Avoid

**④ 用户旅程**（②完成后触发）
- 提示词：第8节
- 输出6阶段摩擦热力图

**流式输出节奏**：
```
T+15s  商品卡片（Phase 1 完成）
T+40s  视觉分析摘要
T+60s  VOC 核心痛点 Top3 + PSPS 画像
T+90s  KANO / $APPEALS 结论
T+110s Must Copy / Must Avoid
T+130s 用户旅程摩擦点
T+150s "报告生成中..."
```

---

### Phase 5：生成报告

**组装 data.json**：
```json
{
  "product":          {},
  "reviews_analysis": {},
  "image_analysis":   "",
  "teardown":         {},
  "reviews_meta":     {"total": 0, "status": "done|partial|insufficient", "note": ""},
  "journey_map":      {}
}
```

`reviews_analysis` 中包含两个新字段（由 Phase 4 AI 输出，格式见 `references/analysis-prompts.md` 第3节）：
- `review_summary`：好差评维度汇总，含 `positive[]`、`negative[]`、`overall_verdict`
- `innovation`：产品创新机会，含 `summary` 和 `opportunities[]`

好评数据不可用时：`review_summary.positive` 为空数组，`innovation` 仅基于差评推导。

**生成 HTML**：
```bash
python3 {P["scripts"]}/generate-report.py \
  {ASIN}-product.json {ASIN}-report.html {ASIN}-data.json
```

**验证**：
```bash
python3 {P["scripts"]}/validate-report.py \
  {ASIN}-report.html --type single --data {ASIN}-data.json
```

验证失败时：
- AI 读报错信息，定位问题
- 修复 data.json 或重新调用 generate-report.py
- 不降级生成 fallback，先尝试修复
- 修复2次仍失败 → 输出 fallback 文字版，告知用户

**Canvas 展示**：
```
canvas present url: file://{ASIN}-report.html
```

---

### 异常处理原则

| 情况 | 处理方式 |
|------|---------|
| 商品页反爬 | 刷新重试，换站点，不卡死 |
| Apify 额度耗尽 | 记录 exhausted_at，静默切浏览器 |
| 评论 < 20 条 | 标注"差评极少"，继续分析 |
| 报告生成失败 | AI 读错误自己修，修2次失败输出文字版 |
| 任何脚本报错 | AI 读 stderr，定位原因，能修就修，不能修就告诉用户 |

**用户感知到的异常提示**（措辞参考）：
- 评论不足：「该商品差评较少（共X条），分析基于现有数据，结论供参考」
- 采集受限：「Amazon 限制了翻页，已采集X条，基于现有数据分析...」
- 报告问题：「报告生成遇到小问题，正在修复...」

---

## AI 写代码规范（必须遵守）

### 写→验→修→继续

```bash
# 1. 分段写入（每段 ≤ 100 行）
cat > /tmp/script.py << 'EOF'
# 第一段
EOF
cat >> /tmp/script.py << 'EOF'
# 第二段（如有）
EOF

# 2. 立即验证（写完所有段后）
python3 -m py_compile /tmp/script.py && echo "✅ OK" || echo "❌ 有错误，停止执行"

# 3. 有错误：读报错，定位行号，原地修复，重新验证
# 4. 通过后执行
python3 /tmp/script.py
```

### 高频错误预防

```python
# ❌ f-string 内嵌同类引号
html = f'<div>{d["key"]}</div>'
# ✅ 改用拼接
html = '<div>' + d["key"] + '</div>'

# ❌ onerror 引号冲突
'<img onerror="this.style.display="none"">'
# ✅ 用转义
'<img onerror="this.style.display=\'none\'">'

# ❌ Amazon aspects 字段名猜测
item.get('sentiment')
# ✅ 正确字段名
item.get('aspectSentiment')
```

### exec 大小自判断

- ≤ 100 行：一次写完
- 100–300 行：主动拆 2–3 段
- > 300 行：拆 4+ 段，或复用已有脚本

---

## 品类总览模式（Phase 6–7）

> 触发：10+ ASIN / Excel 文件 / "品类分析/竞品总览"
> 输出：`report-PSPS-{YYYYMMDD-HHMMSS}.html`

### Phase 6：数据加载

```
Excel 文件 → openpyxl 读取
  Sheet1「商品主数据」：ASIN/Title/Price/Rating/ReviewCount/MainImage/AllImages/视觉AI分析
  Sheet2「评论数据」：ASIN/rating/reviewText/aspects/reviewsAISummary（30列）

JSON 目录 → 读取各 {ASIN}-data.json

纯 ASIN 列表 → 先走单品批量流程，完成后进 Phase 7
```

**aspects 字段解析（关键，字段名是 aspectSentiment）**：
```python
import ast, re

def parse_aspects(s):
    if not s or str(s) == 'None':
        return []
    try:
        result = ast.literal_eval(str(s))
        if isinstance(result, list):
            return [{'aspectName': i.get('aspectName',''),
                     'sentiment':  i.get('aspectSentiment', i.get('sentiment',''))}
                    for i in result if isinstance(i, dict)]
    except:
        pass
    matches = re.findall(
        r"'aspectName'\s*:\s*'([^']+)'.*?'aspectSentiment'\s*:\s*'([^']+)'",
        str(s))
    return [{'aspectName': m[0], 'sentiment': m[1]} for m in matches]
```

### Phase 7：数据处理

AI 直接组装 `batch/category-data.json`，遵守写→验→修→继续规范。

**⚠️ 必须严格按以下 schema 生成，字段名与 `generate-category.py` 完全对应：**

```json
{
  "meta": {
    "total_products": 5,
    "avg_rating": 4.3,
    "total_reviews": 2500,
    "neg_rate": 18.5
  },
  "products": [
    {
      "asin": "B0XXXXXXXX",
      "title": "商品标题",
      "price": "$19.99",
      "rating": 4.2,
      "review_count": 500,
      "one_liner": "一句话核心点评",
      "absa": [
        {"name": "方面名", "positive": 80, "negative": 40, "mixed": 15}
      ]
    }
  ],
  "category_analysis": {
    "psps": {
      "persona": [
        {"label": "用户画像名称", "count": 45},
        {"label": "第二画像", "count": 30}
      ],
      "scenario": [
        {"label": "使用场景", "count": 52},
        {"label": "第二场景", "count": 20}
      ],
      "pain": [
        {"label": "痛点描述（来自关键词频次）", "count": 27},
        {"label": "第二痛点", "count": 16}
      ]
    },
    "absa": [
      {"name": "方面名称", "positive": 140, "negative": 210, "mixed": 35}
    ],
    "appeals": {
      "Price": 55, "Performance": 28, "Packaging": 48,
      "Ease": 22, "Assurances": 20, "LifeCycle": 12, "Social": 38
    },
    "kano": {
      "must_be":     ["基础需求1", "基础需求2"],
      "performance": ["期望需求1"],
      "attractive":  ["魅力需求1"],
      "indifferent": ["无差异需求1"],
      "reverse":     ["反向需求1"]
    },
    "pain_joy_itch": {
      "pain":  ["痛点1", "痛点2"],
      "joy":   ["爽点1", "爽点2"],
      "itch":  ["痒点1", "痒点2"]
    },
    "journey": [
      {"stage": "搜索发现", "friction": "摩擦描述", "score": 6}
    ],
    "ai_summary": {
      "competition": "竞争格局文字",
      "persona":     "用户画像文字",
      "opportunity": "机会点文字",
      "risk":        "风险点文字",
      "advice":      "入场建议文字"
    }
  }
}
```

**PSPS 频次计算规则（必须执行，不得用占位符 1）：**
- `pain.count` → 直接从各单品 `keywords[].count` 汇总同类关键词的总频次
- `persona.count` → 基于各 ASIN 评论数 × 受众相关性估算（标注"推算"）
- `scenario.count` → 基于评论中场景词（gift/birthday/school等）出现频次估算

验证：`category_analysis.psps` 非空，且每个条目有 `label`+`count` 字段；`absa` 非空；`products` 每项有 `absa`。

### Phase 8：品类报告生成

```bash
python3 {P["scripts"]}/generate-category.py \
  {P["batch"]}/category-data.json \
  {P["reports"]}/category-report.html
```

> `generate-category.py` 已存在于 scripts/ 目录，直接调用即可。输入文件是 `batch/category-data.json`（Phase 7 输出），不是 `/tmp/report_data.json`。

报告固定结构（9部分）：第0部分Dashboard / AI总结 / PSPS / ABSA / $APPEALS / KANO / 痛爽痒 / 用户旅程 / ASIN拆解

视觉规范：`references/report-spec.md`

验证：
```bash
python3 {P["scripts"]}/validate-report.py \
  {P["reports"]}/category-report.html --type category --data {P["batch"]}/category-data.json
```

---

## 存档结构

路径由 `scripts/paths.py` 动态解析，结构如下：

```
{P["workspace"]}/          # Mac: ~/.openclaw/workspace | Win: %APPDATA%/openclaw/workspace
├── batch/
│   ├── queue.txt
│   ├── status.json        # failedAt / note 精确记录
│   └── batch-*.log
├── memory/
│   └── apify-token-state.json   # exhausted_at 冷却状态
└── reports/
    └── {ASIN}/
        ├── {ASIN}-product.json
        ├── {ASIN}-reviews-raw.json
        ├── {ASIN}-reviews-positive.json
        ├── {ASIN}-reviews-meta.json
        ├── {ASIN}-data.json
        └── {ASIN}-report.html
```

---

## 参考文件

- `references/analysis-prompts.md` — 8个专家角色完整提示词
- `references/domain-map.md` — 站点映射 + Apify Actor 说明
- `references/report-spec.md` — 品类报告视觉规范
- `scripts/apify-reviews.sh` — Apify Level 1 评论爬取
- `scripts/scrape-reviews.py` — 评论采集主控（降级链 + 硬出口）
- `scripts/generate-report.py` — 单品报告渲染（固定脚本）
- `scripts/generate-category.py` — 品类报告渲染（固定脚本，待创建）
- `scripts/validate-report.py` — 报告结构校验 + fallback
- `scripts/batch-run.sh` — 批量队列调度
- `scripts/generate-batch-summary.py` — 批量汇总总览
