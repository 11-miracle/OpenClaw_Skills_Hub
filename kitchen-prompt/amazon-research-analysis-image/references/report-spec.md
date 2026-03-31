# Amazon APPEALS 报告规范

本参考定义 `amazon-appeals-analysis` 最终报告包的必需结构。除非用户明确只要单一格式，默认交付为同一逻辑表生成的一份本地 `HTML` 报告 + 一份本地 `Excel` 工作簿。

## 1. 适用性检查

仅在以下场景使用本结构：
- 单一产品的大规模评论池，或
- 多个“购买任务一致、核心功能一致、用户语境一致”的相似产品评论池

若产品不可比，不应使用本规范做聚合报告。

## 2. 逻辑表

即使不导出为 CSV/Excel，也应按以下 6 张逻辑表完成推理。`$APPEALS` 仍是核心问题分类脊柱；痛点/爽点/痒点是建立在核心问题分析上的机会层总结。

### `review_voice_pool`

一条评论一行。推荐字段：
- `asin`
- `brand`
- `product_title`
- `rating`
- `review_date`
- `original_text`
- `chinese_interpretation`
- `emotion_major`
- `emotion_type`
- `journey_stage`
- `appeals_l1`
- `appeals_l2`
- `appeals_type`
- `emotion_reason`
- `keyword_list`
- `severity_score`
- `confidence`

### `emotion_summary`

按情绪聚合。最小字段：
- `emotion_major`
- `emotion_type`
- `count`
- `share`
- `reason`
- `keywords`
- `representative_comment`

### `journey_summary`

按旅程阶段聚合。最小字段：
- `journey_stage`
- `count`
- `share`
- `top_emotions`
- `top_appeals`
- `unmet_need`
- `representative_comment`

### `appeals_l1_summary`

按 APPEALS 一级维度聚合。最小字段：
- `appeals_l1`
- `count`
- `share`
- `avg_severity`
- `top_keywords`
- `top_reason`

### `appeals_l2_summary`

按 APPEALS 二级问题聚合。最小字段：
- `appeals_l1`
- `appeals_l2`
- `appeals_type`
- `count`
- `share`
- `avg_severity`
- `priority_score`
- `top_emotion_major`
- `top_emotion_type`
- `emotion_reason`
- `top_keywords`
- `improvement_suggestion`
- `representative_comment`

### `pain_pleasure_itch_summary`

按需求机会维度聚合。最小字段：
- `need_dimension`（`Pain | Pleasure | Itch`）
- `evidence_level`（`direct | insufficient`）
- `pain_strength`（`strong | weak`）
- `usage_frequency`（`high | low`）
- `matrix_quadrant`
- `count`
- `share`
- `related_appeals`
- `related_journey_stage`
- `user_state`
- `product_strategy`
- `opportunity_statement`
- `representative_comment`

字段规则：
- `pain_strength` 需依据严重度、紧迫性、以及“是否不可回避”综合判定。
- `usage_frequency` 需依据提及密度与使用场景重复度判定。
- `matrix_quadrant` 必须映射到四象限之一：`刚需高频`、`刚需低频`、`爽点驱动`、`痒点驱动`。
- `evidence_level` 默认使用 `direct` 或 `insufficient`，尤其在低星样本下避免把推断写成事实。

## 3. HTML 结构

最终 HTML 必须是白底分析报告，而非营销落地页。

必备模块：
1. 顶部摘要卡，主要标题是XXX分析报告
2. 用户情绪分析
3. 用户旅程分析
4. `$APPEALS` 需求分析
5. 痛点-爽点-痒点矩阵
6. 行动建议
7. 证据附录

痛点-爽点-痒点模块必须包含：
- `Pain`、`Pleasure`、`Itch` 三张摘要卡
- 一个 2x2 矩阵区域（横轴 `高频/低频使用`，纵轴 `强/弱痛点`）
- 每个象限在证据存在时给出 1-3 条机会点
- 当低星证据无法验证 `Pleasure` / `Itch` 时，明确显示“仅验证到痛点，爽点/痒点证据不足”类提示

## 4. Excel 工作簿结构

Excel 是同一分析的必需配套格式，应是干净白底报告，而非原始数据堆叠。

必需 sheet 顺序：
1. `报告总览`
2. `情绪分析`
3. `旅程分析`
4. `APPEALS分析`
5. `痛点爽点痒点`
6. `行动建议`
7. `证据附录`

最小工作簿规则：
- 报告式布局：模块清晰、填色克制、边框纤细、间距可读
- 各表冻结首行表头
- 长文本需换行并控制列宽，避免强制横向溢出
- 行高需按换行内容自适应增长，确保评论、原因、建议、解释等长文本完整可读（含中文全角文本）
- 图表使用原生 Excel 图表，不依赖截图粘贴

各 sheet 最小内容：
- `报告总览`：标题区、样本说明、KPI 区、Top 问题表、Top 机会表、至少 2 个小图
- `情绪分析`：主情绪表、情绪类型明细表、至少 1 张图
- `旅程分析`：阶段汇总表、至少 1 张图
- `APPEALS分析`：一级维度汇总、二级问题 Top 表、全页至少 2 张图
- `痛点爽点痒点`：三维汇总 + 可视 2x2 矩阵单元格；若 `Pleasure` 或 `Itch` 未验证，需突出 `证据不足`
- `行动建议`：Top 建议表，突出优先级
- `证据附录`：完整或按用户限制后的证据行，含可筛选表头、英文原文、中文解释

## 5. 图表要求

报告包应包含以下图表类型或等价形式：
- 情绪分布图
- 旅程阶段问题量图
- `$APPEALS` 一级维度分布图
- 二级问题优先级图
- 痛点-爽点-痒点矩阵图
- 证据筛选区

图表可用纯 HTML/CSS/SVG 或轻量本地离线方案实现，不应依赖服务器。

## 6. 证据附录

附录是唯一强制保留来源级细节的区域。

应保留：
- 英文评论原文
- 中文解释
- 来源 `ASIN`
- 来源 `brand`
- 来源 `product title`

建议至少支持以下筛选：
- 关键词
- APPEALS 维度
- 情绪或旅程阶段（可行时）

## 7. 命名规则

推荐文件名：
- `report-YYYYMMDD-HHMMSS.html`
- `report-YYYYMMDD-HHMMSS.xlsx`

若用户未指定保存位置：
- 保存到工作区 `output/`
- 同一次报告生成中，HTML 与 Excel 使用同一时间戳

## 8. 样本注意事项

若样本仅包含低星评论：
- 明确声明所有占比均在低星样本内计算
- 不可伪造正负平衡
- 无正样本证据时不可声称已验证优势项
- `Pain` 可完整分析；`Pleasure` 与 `Itch` 除非有明确证据，否则必须标注 `证据不足`，不得用“补全文案”替代证据

若样本包含多个产品：
- 主报告保持聚合视角
- 仅在用户明确要求时展示来源产品差异

## 9. 风格规则

- 默认语言：中文
- 证据附录：英文原文 + 中文解释
- 视觉风格：白底卡片、细边框、克制间距、高信息密度
- 移动端行为：自然单列折叠，不出现水平滚动
- Excel 风格：白底画布、深蓝表头、浅蓝分区条、纤细网格、整洁间距，重点项高亮但不过度装饰
- Excel 可读性：换行文本所在行需自动增高，避免隐藏溢出或手动点开
- Excel 字号规则：表格正文默认 `14pt`，标题区可高于该字号


