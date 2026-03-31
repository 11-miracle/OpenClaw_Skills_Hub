---
name: amazon-research-analysis-image
description: 当用户需要把商品采集、证据分析、报告输出和中文生图提示词合并为一个流程时使用。该技能采用 scenario 驱动：agent 负责解析需求并分析，脚本按 scenario 调用 actor 执行采集。
---

# Amazon Research Analysis Image

## Overview

本技能采用三层模式：
- `agent 解析`：把用户需求转为 `scenario`
- `script/actor 执行`：按 `scenario` 完成采集
- `agent 分析`：基于采集结果生成报告和生图提示词

关键点：
- 评论采集为 **Apify-only**
- 首次无 token 时，交互输入并自动保存本地
- 不再写死“只抓双榜、只抓前10”这类逻辑，改为 `scenario` 控制

## Scenario 契约

核心字段：
- `platform`: 当前默认 `amazon`
- `seed_mode`: `asin | keyword`
- `input`: 关键词或 ASIN
- `domain`: 站点域名
- `intent`: `quick | standard | deep | batch`
- `scope`: `bestsellers | new_releases | both`
- `top_n`: 候选数量
- `outputs`: `both | report | prompt`
- `review_policy`: `fast | balanced | strict`

## 原子执行步骤

### A1. 需求解析 -> scenario

工具：
- `scripts/resolve_scenario.py`

目标：
- 将自然语言约束（如“销量前十”）映射为结构化参数（如 `scope=bestsellers, top_n=10`）

### A2. 采集执行（script/actor）

工具：
- `scripts/run-amazon-collect.sh`
- 底层：`scripts/run-research.sh`

执行链：
- 搜索：`scripts/search-amazon.sh`（按 `scope/top_n/platform` 调 actor）
- 商品：`scripts/batch-scrape-products.sh`
- 评论：`scripts/batch-scrape-reviews.sh` -> `scripts/scrape-reviews-batch.py` -> `scripts/apify-reviews-batch.sh`

### A3. 报告输入标准化

工具：
- `scripts/prepare_report_base.py --run-dir <run_dir>`

### A4. 报告生成

工具：
- `scripts/generate_multi_asin_report.py --base-dir <report_base> --format both|html|excel`

### A5. 生图提示词生成

工具：
- `scripts/generate_image_prompt_cn.py --run-dir <run_dir>`

## 默认输出

- 报告路径（HTML/Excel）
- `product_description_cn`
- `image_prompt_structured_cn`
- `negative_prompt_cn`

## 命令示例

### 1) 从自然语言生成 scenario

```bash
python3 scripts/resolve_scenario.py \
  --input "B0G8DV5BJT" \
  --request "采集这个asin下销量前十，生成可视化报告和生图提示词" \
  --out /tmp/scenario.json
```

### 2) 仅采集（按 scenario）

```bash
bash scripts/run-amazon-collect.sh --scenario-file /tmp/scenario.json
```

### 3) 采集+分析全流程

```bash
bash scripts/run-analysis-flow.sh --scenario-file /tmp/scenario.json --format both
```

### 4) 直接参数运行（不先写 scenario）

```bash
bash scripts/run-analysis-flow.sh \
  --input "B0G8DV5BJT" \
  --platform amazon \
  --domain amazon.com \
  --scope bestsellers \
  --top-n 10 \
  --outputs both \
  --review-policy balanced \
  --format both
```

## Token 与路由

- token 自动加载/首次保存：`scripts/_apify-run.sh`
- actor 路由配置：`scripts/actor-map.json`

## 产物路径

`run_dir` 下关键文件：
- `scenario.json`
- `execution-plan.json`
- `search-results.json`
- `products/*.json`
- `reviews/*-reviews.json`
- `summary.json`
- `artifacts.json`
- `output/report-*.html`
- `output/report-*.xlsx`
- `output/image-prompt-cn.md`
