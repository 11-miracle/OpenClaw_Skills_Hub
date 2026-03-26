#!/usr/bin/env bash
# browser-reviews.sh — 浏览器自动化爬取亚马逊差评（Level 2 降级方案）
# 用法: bash browser-reviews.sh <ASIN> [domain] [max_reviews] [output_file]
#
# 退出码：
#   0 = 成功有数据
#   2 = 成功但数据不足（< 20条），需要 Level 3
#   4 = 无 next page 按钮，需要 Level 3
#   1 = 失败

set -uo pipefail

ASIN="${1:?需要提供 ASIN}"
DOMAIN="${2:-amazon.com}"
MAX_REVIEWS="${3:-200}"
OUTPUT_FILE="${4:-/tmp/browser-reviews-${ASIN}.json}"

REVIEWS_URL="https://www.${DOMAIN}/product-reviews/${ASIN}?filterByStar=critical&sortBy=recent&pageNumber=1"
LOGIN_CHECK_URL="https://www.${DOMAIN}"

# ── Python 脚本：通过 OpenClaw browser 工具完成所有操作 ──────────
# 实际由 AI（卡布达）在 SKILL.md 流程中调用 browser 工具执行
# 本脚本输出操作指令供 AI 参考，实际爬取由 AI 的 browser tool 完成

echo "📋 [Browser] 操作目标: ${REVIEWS_URL}" >&2
echo "📋 [Browser] 目标条数: ${MAX_REVIEWS}" >&2

# 输出结构化指令（供 SKILL.md 流程中 AI 读取执行）
cat <<EOF
{
  "action": "browser_reviews",
  "asin": "${ASIN}",
  "domain": "${DOMAIN}",
  "max_reviews": ${MAX_REVIEWS},
  "output_file": "${OUTPUT_FILE}",
  "steps": [
    {
      "step": 1,
      "name": "check_login",
      "description": "打开亚马逊首页，检测登录状态",
      "url": "${LOGIN_CHECK_URL}",
      "detect_logged_in": "页面包含用户名（非 'Hello, sign in'）",
      "on_not_logged_in": "聊天框提示用户登录，等待「继续」或「跳过」"
    },
    {
      "step": 2,
      "name": "open_reviews",
      "description": "打开差评页面",
      "url": "${REVIEWS_URL}"
    },
    {
      "step": 3,
      "name": "check_next_page",
      "description": "检测是否有 next page 按钮",
      "selector": "li.a-last:not(.a-disabled) a",
      "on_no_next_page": "exit_code=4，触发 Level 3"
    },
    {
      "step": 4,
      "name": "scrape_and_paginate",
      "description": "循环翻页抓取评论，每页解析评论条目",
      "fields": ["rating", "title", "body", "date", "verified", "reviewer"],
      "max_pages": 20,
      "stop_when": "无 next page 或达到 max_reviews"
    },
    {
      "step": 5,
      "name": "save_output",
      "description": "保存 JSON 到 output_file",
      "output_file": "${OUTPUT_FILE}"
    }
  ]
}
EOF
