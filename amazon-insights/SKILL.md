---
name: amazon-insights
description: 亚马逊商品洞察分析。支持两种模式：①单品/批量分析——用户说"帮我收集/分析/爬取/查一下/选品/拆解竞品 [ASIN]"时触发，通过爬取+AI分析输出单品HTML报告；②品类总览报告——用户提供Excel离线数据文件、10+个ASIN、或说"品类分析/竞品总览/生成可视化报告"时触发，输出含9部分的品类级HTML洞察报告（含AI动态总结）。方法论：PSPS · $APPEALS(8维) · KANO(5类) · ABSA方面级情感 · 痛爽痒矩阵 · 用户旅程地图。
---

# Amazon Insights Skill

## ⚡ 模式判断路由（入口，必须先执行）

拿到用户输入后，**第一步**判断走哪条路：

| 输入类型 | 判断条件 | 执行路径 |
|---------|---------|---------|
| 单个 ASIN | 1个10位字母数字 | → **单品模式**（Step 1-5） |
| 少量 ASIN | 2-9个 ASIN | → **批量模式**（Step 1-5 循环 + Step 6 汇总） |
| 大批量 / 离线文件 | 10+个ASIN，或用户给了Excel/JSON文件路径，或说"品类分析/竞品总览/可视化报告" | → **品类总览模式**（Step 7） |

**判断优先级**：文件路径 > ASIN数量 > 关键词

---

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

## ═══════════════════════════════════
## 单品 / 批量模式（Step 1-6）
## ═══════════════════════════════════

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

**线程A：商品基础信息**
```bash
bash ~/openclaw/skills/amazon-insights/scripts/scrape-product.sh <ASIN> <domain>
```
完成后：立即流式输出商品卡片到聊天框，触发 ① 图片视觉分析 + ③ 单品拆解（并行）

**线程B：评论爬取（三级降级链 + 自动站点切换）**
```
Level 1: Apify（90s 硬超时）
    ↓ 0条 / 超时 / 失败
Level 2: 浏览器自动化翻页
    ├─ 登录检测 → 已登录直接翻页 / 未登录提示用户
    ├─ 翻页循环：while 已采集 < 目标数 and hasNext
    └─ 采集结果 < 100 → 触发自动站点切换
Level 3: 自动站点切换
    切换顺序: amazon.com → amazon.co.uk → amazon.de → amazon.co.jp
    各站结果合并去重（按 title+body 前50字）
    全部站点合计 < 100 → 标注说明，继续分析
```

**Level 2 翻页 JS：**
```javascript
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

---

### Step 3：分析层（流式推送）

> 每个专家分析完立即输出一段到聊天框，不等全部完成

**① 商品图视觉分析**（线程A完成后）：读 `references/analysis-prompts.md` 第1节，输入前5张图，完成后推送视觉摘要

**② 需求分析师 VOC**（线程B完成后）：读第3节，非中文评论先翻译（第7节，50条/批），3星评论完整保留（含正面内容供爽点/痒点提取），输出结构化 JSON：`psps` / `absa` / `keywords` / `appeals` / `kano` / `pain_pleasure_itch` / `opportunity` / `radar_expect` / `radar_actual` / `sample_reviews`

**③ 单品拆解专家**（①完成后）：读第4节，输出 `teardown.must_copy` / `must_avoid` / `conclusion` / `identity_tag`

**④ 竞品可视化拆解**（①②均完成后）：读第5节，输出文字报告嵌入最终 HTML

**⑦ 用户旅程分析师**（②完成后，与③④并行）：读第8节，输出 `journey_map`（6阶段）/ `top3_friction_stages` / `peak_end_insight` / `journey_optimization_actions`

---

### Step 4：整合数据

组装 `$REPORT_DIR/<ASIN>-data.json`（结构详见 `references/report-spec.md`）

---

### Step 5：生成单品报告（7模块）

```bash
python3 ~/openclaw/skills/amazon-insights/scripts/generate-report.py \
  <ASIN>-product.json <ASIN>-report.html <ASIN>-data.json
```

**报告固定结构：**
1. Header（ASIN + 站点 + 生成时间 + 身份标签）
2. 基础信息（标题/价格/评分/五点/主图）
3. 详情图 & 视觉分析
4. 差评分析（采集说明 + 关键词 + APPEALS玫瑰图 + KANO表格 + 雷达图 + 机会点）
5. 单品拆解（Must Copy / Must Avoid / 结论）
6. 差评原声剧场（最多9条）
7. Footer

**验证**：HTML < 50KB 视为失败，重新执行

**流式输出顺序：**
```
T+30s  → 商品卡片（标题/价格/评分）
T+50s  → 视觉分析摘要
T+60s  → 单品拆解结论
T+90s  → VOC差评摘要（PSPS + 痛爽痒强度 + ABSA危机预警）
T+110s → 旅程摩擦热力图摘要
T+150s → 最终报告路径 + Canvas展示
```

---

### Step 6：批量模式

```bash
bash ~/openclaw/skills/amazon-insights/scripts/batch-run.sh
bash ~/openclaw/skills/amazon-insights/scripts/batch-status.sh
python3 ~/openclaw/skills/amazon-insights/scripts/generate-batch-summary.py
```

汇总报告：`~/.openclaw/workspace/reports/batch-summary.html`（进度条 + KPI + ASIN明细表 + 报告链接，每60秒自动刷新）

---

### 评论采集规范

| 参数 | 规则 |
|------|------|
| 星级 | 3星及以下 |
| 最少数量 | **100条**（硬门槛） |
| 上限 | **1000条** |
| 默认目标 | 200条 |
| 不足处理 | 自动切换站点，全部失败输出⚠️说明继续分析 |

---

### 错误处理（单品/批量）

| 情况 | 处理 |
|------|------|
| 商品爬取失败 | 降级用 browser 工具抓取，标注来源 |
| 所有站点评论 < 100 | 报告第4模块顶部输出⚠️说明，继续分析 |
| Apify token 耗尽 | 静默切 Level 2，不中断流程 |
| 评论 < 20 条 | 标注"差评极少，分析仅供参考" |
| HTML < 50KB | 视为失败，重新执行 generate-report.py |
| 批量某个 ASIN 失败 | 记录 failed 状态，跳过继续下一个 |

---

### 存档结构

```
~/.openclaw/workspace/
├── batch/
│   ├── queue.txt
│   ├── status.json
│   └── batch-*.log
└── reports/
    ├── batch-summary.html
    └── <ASIN>/
        ├── <ASIN>-product.json
        ├── <ASIN>-reviews-raw.json
        ├── <ASIN>-reviews-meta.json
        ├── <ASIN>-data.json
        └── <ASIN>-report.html
```


---


## ═══════════════════════════════════
## Step 7：品类总览模式（离线文件 / 10+ASIN）
## ═══════════════════════════════════

> 触发条件：用户给了 Excel/JSON 离线文件，或 10+个ASIN，或说"品类分析/竞品总览/可视化报告"
> 输出：单文件 HTML 品类洞察报告，路径：{用户指定目录}/report-PSPS-{YYYYMMDD-HHMMSS}.html

### ⚠️ 执行前强制检查（防止 run error: terminated）

1. 所有 Python 脚本必须先用 `cat > /tmp/xxx.py << 'PYEOF'` 写入文件，再用 `python3 /tmp/xxx.py` 执行
2. 单次 `cat >>` 追加内容不超过 150 行
3. 数据处理脚本（gen_report_data.py）与 HTML 生成脚本（build_report.py）必须分离
4. 禁止在单次 exec 中直接传入超过 100 行 Python 字符串
5. 禁止用子代理生成 HTML（5分钟超时不够，主会话分段执行最稳定）


### Step 7.1：识别输入数据

```
输入类型判断：
├─ Excel 文件（.xlsx）→ 用 openpyxl 读取
│   ├─ Sheet1「商品主数据」：ASIN / 视觉AI分析 / Title / Price / MainImage / AllImages / Rating / ReviewCount
│   └─ Sheet2「评论数据」：aspects / reviewsAISummary / ASIN / rating / reviewText / ... (30列)
├─ JSON 目录 → 读取各 <ASIN>-data.json 文件
└─ 纯 ASIN 列表（10+）→ 先走单品批量爬取，完成后进入 Step 7.2
```

**Excel 标准路径约定**（用户未指定时询问）：
- 数据文件：`{用户目录}/{品类名}商品主数据+图片理解+评论数据.xlsx`
- 输出报告：`{用户目录}/report-PSPS-{YYYYMMDD-HHMMSS}.html`


### Step 7.2：数据处理脚本（gen_report_data.py）

**职责**：读原始数据 → 计算聚合 → 输出 `/tmp/report_data.json`
**验证**：运行后检查 `absa`、`asinDetails`、`productTable` 字段是否非空

**标准输出结构**：
```json
{
  "meta": { "totalProducts": 52, "avgRating": 4.36, "totalReviews": 855, "negRate": 12.9 },
  "priceDist":    { "$0-20": 7, "$20-40": 15, "$40-60": 4, "$60-80": 5, "$80+": 21 },
  "ratingDist":   { "1": 0, "2": 0, "3": 2, "4": 31, "5": 16 },
  "productTable": [{ "asin":"", "title":"", "price":"", "rating":0, "reviewCount":0, "negCount":0 }],
  "personaWords": { "kids": 515, "child": 169, ... },
  "scenarioTop10": [["gift", 182], ["learning", 128], ...],
  "painTop5":      [["battery", 31], ["waste", 13], ...],
  "absaList": [{ "name":"Functionality", "positive":140, "negative":160, "mixed":160, "neutral":0, "total":460, "negRatio":0.696 }],
  "appealsData": {
    "Price":       { "negTotal": 220, "top3": [{"aspect":"Value for money","negCount":220}] },
    "Performance": { "negTotal": 540, "top3": [...] }
  },
  "kanoList": [{ "aspect":"", "type":"Must-be", "label":"基础型", "color":"#f44336", "total":0, "posRatio":0, "negRatio":0, "strategy":"" }],
  "painData": [{ "kw":"doesn't work", "count":45, "example":"..." }],
  "joyData":  [{ "kw":"love it", "count":234, "example":"..." }],
  "itchData": [{ "kw":"educational", "count":89, "example":"..." }],
  "journeyData":  { "认知/搜索": 13, "购买决策": 33, "配送开箱": 8, "首次使用": 55, "长期使用": 13, "售后客服": 24 },
  "journeyTop3":  { "首次使用": ["example1", "example2"] },
  "asinDetails": [{
    "asin":"", "title":"", "price":"", "rating":0, "reviewCount":0,
    "mainImage":"", "visualSummary":"", "aiSummary":"",
    "aspects": [{ "name":"Fun", "positive":20, "negative":5, "mixed":3, "neutral":2 }],
    "negExcerpts": ["评论原文前150字"]
  }]
}
```


### Step 7.3：已知字段映射（必读，防止数据解析错误）

**⚠️ aspects 字段关键陷阱**：情感字段名是 `aspectSentiment`，不是 `sentiment`

```python
import ast, re

def parse_aspects(aspect_str):
    """解析 aspects 字段 - 情感字段为 aspectSentiment（非 sentiment）"""
    if not aspect_str or str(aspect_str) == 'None':
        return []
    try:
        result = ast.literal_eval(str(aspect_str))
        if isinstance(result, list):
            return [
                {
                    'aspectName': item.get('aspectName', ''),
                    'sentiment':  item.get('aspectSentiment', item.get('sentiment', ''))
                }
                for item in result if isinstance(item, dict) and item.get('aspectName')
            ]
    except:
        pass
    # 降级：正则提取
    matches = re.findall(
        r"'aspectName'\s*:\s*'([^']+)'.*?'aspectSentiment'\s*:\s*'([^']+)'",
        str(aspect_str)
    )
    return [{'aspectName': m[0], 'sentiment': m[1]} for m in matches]
```

**Excel 字段名对照表**：

| 用途 | 实际字段名 | 注意 |
|------|-----------|------|
| aspect 情感 | `aspectSentiment` | ⚠️ 非 sentiment |
| aspect 名称 | `aspectName` | 正常 |
| 评论正文 | `reviewText` | 正常 |
| 评论星级 | `rating` | 用 float() 转换 |
| AI评论总结 | `reviewsAISummary` | 多条评论共享同值，取第一条非空 |
| 视觉AI分析 | `视觉AI分析` | 用正则提取"一句话战略：(.+)" |


### Step 7.4：HTML 生成脚本（build_report.py）

**职责**：读 `/tmp/report_data.json` → 调用 LLM 生成 AI 总结 → 拼接完整 HTML → 写出文件
**验证**：文件大小 > 100KB；结构检查所有9个 `<h2>` 标题存在；ASIN 折叠卡片数量 = 商品总数

**分段写入执行模板**（严格按此执行，每段 ≤ 150 行）：
```bash
# 段1：初始化
cat > /tmp/build_report.py << 'PYEOF'
# 初始化代码（imports + 读数据 + 变量）
PYEOF

# 段2：HEAD + CSS
cat >> /tmp/build_report.py << 'PYEOF'
# HTML head 和 CSS
PYEOF

# 段3：第0部分 Dashboard
cat >> /tmp/build_report.py << 'PYEOF'
PYEOF

# 段4：AI总结调用 + 插入
cat >> /tmp/build_report.py << 'PYEOF'
PYEOF

# 段5：第1-2部分
cat >> /tmp/build_report.py << 'PYEOF'
PYEOF

# 段6：第3-4部分
cat >> /tmp/build_report.py << 'PYEOF'
PYEOF

# 段7：第5-6部分
cat >> /tmp/build_report.py << 'PYEOF'
PYEOF

# 段8：第7部分 ASIN拆解
cat >> /tmp/build_report.py << 'PYEOF'
PYEOF

# 段9：JS初始化 + 写文件
cat >> /tmp/build_report.py << 'PYEOF'
PYEOF

# 统一运行
python3 /tmp/build_report.py
```

**f-string 内嵌引号冲突处理**（必须遵守）：
```python
# ❌ 错误：f-string 内不能再用同类引号
parts.append(f"<div>"{var}"</div>")

# ✅ 正确：改用字符串拼接
parts.append("<div>&ldquo;" + var + "&rdquo;</div>")

# ✅ 正确：HTML 属性用单引号，外层用双引号
block = '<img src="' + img + '" onerror="this.style.display=\'none\'">'
```


### Step 7.5：品类总览报告固定结构（严格按序，不可缺省）

| 编号 | 部分名称 | 数据字段 | 图表 |
|------|---------|---------|------|
| 第0部分 | 品类总览 Dashboard | meta / priceDist / ratingDist / productTable | KPI×4 + 柱状图 + 饼图 + 总览表 |
| 总结部分 | 品类总体分析总结（AI生成） | ai_summary_input.json | 5卡片文字布局 |
| 第1部分 | PSPS 用户画像 | personaWords / scenarioTop10 / painTop5 | 横向条形图×3 |
| 第2部分 | ABSA 方面级情感分析 | absaList | 水平堆叠条形图 |
| 第3部分 | $APPEALS 8维竞争力 | appealsData | 南丁格尔玫瑰图 + 列表 |
| 第4部分 | KANO 需求分类 | kanoList | CSS 彩色表格 |
| 第5部分 | 痛爽痒三维图谱 | painData / joyData / itchData | 三列卡片 |
| 第6部分 | 用户旅程摩擦分析 | journeyData / journeyTop3 | 折线图 + 摩擦卡片 |
| 第7部分 | 逐品 ASIN 拆解 | asinDetails | details折叠卡片×N |

**KANO 分类逻辑**：
- Must-be（基础型）：负面占比 > 60%
- Performance（期望型）：负面占比 30-60%
- Attractive（魅力型）：正面占比 > 80% 且出现次数 > 10
- Indifferent（无差异型）：出现次数 < 5
- Reverse（反向型）：正面和负面都 > 30%

**$APPEALS 8维映射**：
- Price → Value for money / Price / Affordability
- Availability → Shipping / Delivery / Availability
- Packaging → Packaging / Design / Appearance
- Performance → Quality / Functionality / Performance / Durability
- Ease → Ease of use / Setup / Instructions
- Assurances → Customer service / Return / Warranty / Support
- LifeCycle → Durability / Battery / Long-term
- Social → Gift value / Educational value / Fun / Interactiveness


### Step 7.6：AI 总结动态生成规范

**触发时机**：build_report.py 执行时，写第0部分之后、第1部分之前调用

**输入数据提炼**（写入 /tmp/ai_summary_input.json）：
```python
summary_input = {
    "meta": D['meta'],
    "priceDist": D['priceDist'],
    "topPersona": list(D['personaWords'].items())[:8],
    "topScenario": D['scenarioTop10'][:5],
    "crisisAspects": [a for a in D['absaList'] if a['negRatio'] > 0.5][:5],
    "attractiveKano": [k for k in D['kanoList'] if k['type'] == 'Attractive'][:3],
    "topPain": D['painTop5'],
    "topJourney": sorted(D['journeyData'].items(), key=lambda x:-x[1])[:3],
    "appealsTopNeg": sorted(D['appealsData'].items(), key=lambda x:-x[1]['negTotal'])[:4]
}
```

**LLM 调用**（读取本机已配置的 LiteLLM 接口）：
```python
import json, urllib.request
with open('/Users/macmini/.openclaw/openclaw.json') as f:
    cfg = json.load(f)
litellm = cfg['models']['providers']['litellm']
payload = json.dumps({
    "model": "claude-sonnet-4-6",
    "messages": [{"role": "user", "content": PROMPT}],
    "max_tokens": 2000, "temperature": 0.3
}).encode('utf-8')
req = urllib.request.Request(
    litellm['baseUrl'] + '/v1/chat/completions',
    data=payload,
    headers={"Content-Type":"application/json","Authorization":"Bearer "+litellm['apiKey']}
)
with urllib.request.urlopen(req, timeout=60) as resp:
    ai_html = json.loads(resp.read())['choices'][0]['message']['content'].strip()
# 去除可能的 markdown 包裹
if ai_html.startswith('```'): ai_html = '\n'.join(ai_html.split('\n')[1:])
if ai_html.endswith('```'):   ai_html = '\n'.join(ai_html.split('\n')[:-1])
```

**Prompt 模板**（已验证可用）：
```
你是资深亚马逊品类分析师。基于以下数据为"{品类名}"品类生成【品类总体分析总结】HTML片段。

数据：{summary_input}

输出5个分析卡片（纯HTML inline style，中文，不含markdown）：
1. 📊 竞争格局：品类成熟度、价格带分布、竞争强度（2-3句）
2. 👥 核心用户画像：谁在买、为什么买、主要场景（2-3句）
3. 🚀 Top3机会点：具体可操作，每条一句，绿色高亮
   样式：background:#e8f5e9;border-left:4px solid #1b5e20;padding:8px 12px;margin:6px 0
4. ⚠️ Top3风险点：基于危机aspects和痛点，每条一句，红色高亮
   样式：background:#ffebee;border-left:4px solid #b71c1c;padding:8px 12px;margin:6px 0
5. 💡 入场建议：差异化策略，2-3句
   样式：background:#fff3e0;border-left:4px solid #e65100;padding:8px 12px

布局：卡片1+2用 display:grid;grid-template-columns:1fr 1fr;gap:16px 包裹，3-5各自独立
卡片样式：background:#fff;border:1px solid #e0e0e0;padding:20px;margin-bottom:16px
标题样式：font-size:16px;font-weight:700;color:#2c3e50;margin-bottom:12px
正文样式：font-size:13px;line-height:1.7;color:#444
```


### Step 7.7：视觉规范（品类报告）

```
背景：#f5f5f5（页面）/ #ffffff（卡片）
主色：#2c3e50
警示色：#b71c1c（危机/风险）
机会色：#1b5e20（机会点）
卡片：border:1px solid #e0e0e0，无圆角，无阴影
字体：-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
容器：max-width:1400px; margin:0 auto; padding:24px
ECharts CDN：https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js
ASIN 图表 id：chart-{ASIN}（唯一，在 ontoggle 事件中初始化，防止折叠前渲染）
```

**第7部分 ASIN 图表初始化方式**（必须用 ontoggle，不能在 window.onload）：
```html
<details id="{asin}" ontoggle="initAsinChart(this,'{asin}',{asp_names},{asp_pos},{asp_neg},{asp_mix})">
```
```javascript
var _initedCharts = {};
function initAsinChart(el, asin, names, pos, neg, mix) {
  if (!el.open || _initedCharts[asin]) return;
  _initedCharts[asin] = true;
  var c = echarts.init(document.getElementById('chart-' + asin));
  c.setOption({ /* 堆叠条形图 */ });
}
```

### Step 7.8：错误处理（品类模式）

| 错误 | 原因 | 修复方式 |
|------|------|---------|
| `run error: terminated` | exec 单次内容过大 | 改用 `cat > file << 'EOF'` 写文件后运行 |
| `SyntaxError` 在 f-string 内 | 内嵌引号冲突 | 改用字符串拼接，不用 f-string |
| `ABSA aspects: 0` | 字段名用了 `sentiment` | 必须用 `aspectSentiment`，见 Step 7.3 |
| 文件 < 100KB | AI总结未生成或数据为空 | 检查 LLM 调用；检查 asinDetails 是否有数据 |
| AI总结调用失败 | 网络超时或接口异常 | 降级：用固定模板文字替代，不阻断报告生成 |
| `totalReviews` 异常偏大 | ReviewCount 字段含总评论数非负评数 | meta.totalReviews 用 len(reviews)，不用 sum(ReviewCount) |


---

## 参考文件

- `references/analysis-prompts.md` — 6个专家角色完整提示词
- `references/domain-map.md` — 站点映射 + 降级链配置
- `references/report-spec.md` — 单品报告规范文档
- `scripts/scrape-product.sh` — 商品信息爬取
- `scripts/apify-reviews.sh` — Apify Level 1 评论爬取
- `scripts/browser-reviews.py` — Level 2 浏览器自动化
- `scripts/run-pipeline.sh` — 并行调度主脚本
- `scripts/generate-report.py` — 单品报告生成（7模块）
- `scripts/batch-run.sh` — 批量队列调度
- `scripts/batch-status.sh` — 批量进度查看
- `scripts/generate-batch-summary.py` — 批量汇总总览生成
