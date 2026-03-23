#!/usr/bin/env bash
# run-pipeline.sh — 并行调度主脚本
# 用法: bash run-pipeline.sh <ASIN> [domain] [max_reviews]
#
# 执行策略：
#   - 线程A（商品信息）和线程B（评论爬取）同时启动
#   - 线程A完成后立即流式输出商品卡片，触发①③分析
#   - 线程B：Apify 90s超时 → Level2 浏览器自动化 → Level3 站点切换
#   - 评论到手后触发②VOC翻译+分析 → ④竞品拆解
#
# 退出码输出到 PIPELINE_STATUS_FILE，供调用方读取

set -uo pipefail

ASIN="${1:?需要提供 ASIN}"
DOMAIN="${2:-amazon.com}"
MAX_REVIEWS="${3:-200}"
REPORT_DIR="${HOME}/.openclaw/workspace/reports/${ASIN}"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="${SKILL_DIR}/scripts"

# 状态文件（各步骤完成时写入，供 AI 主流程轮询）
STATUS_DIR="/tmp/pipeline-${ASIN}"
mkdir -p "$STATUS_DIR" "$REPORT_DIR"

PRODUCT_DONE="${STATUS_DIR}/product.done"
REVIEWS_DONE="${STATUS_DIR}/reviews.done"
REVIEWS_LEVEL="${STATUS_DIR}/reviews.level"   # 记录用了哪个 Level
PIPELINE_LOG="${STATUS_DIR}/pipeline.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$PIPELINE_LOG" >&2; }

# ── 线程A：商品信息采集 ─────────────────────────────────────────
thread_product() {
  log "▶ [线程A] 启动商品信息爬取..."
  local product_file="${REPORT_DIR}/${ASIN}-product.json"

  if bash "${SCRIPTS_DIR}/scrape-product.sh" "$ASIN" "$DOMAIN" > "$product_file" 2>>"$PIPELINE_LOG"; then
    local title
    title=$(python3 -c "import json; d=json.load(open('$product_file')); print(d.get('title','')[:40])" 2>/dev/null || echo "")
    log "✅ [线程A] 商品信息完成: ${title}"
    echo "ok" > "$PRODUCT_DONE"
  else
    log "⚠️  [线程A] scrape-product 失败，标记降级"
    echo "fallback" > "$PRODUCT_DONE"
  fi
}

# ── 线程B：评论爬取（带降级链） ──────────────────────────────────
thread_reviews() {
  log "▶ [线程B] 启动评论爬取（Level 1: Apify）..."
  local reviews_file="${REPORT_DIR}/${ASIN}-reviews-raw.json"

  # Level 1: Apify（90s 超时）
  local apify_exit=0
  bash "${SCRIPTS_DIR}/apify-reviews.sh" "$ASIN" "$DOMAIN" "$MAX_REVIEWS" \
    > "$reviews_file" 2>>"$PIPELINE_LOG" || apify_exit=$?

  local count=0
  count=$(python3 -c "import json; print(len(json.load(open('$reviews_file'))))" 2>/dev/null || echo "0")

  if [ $apify_exit -eq 0 ] && [ "$count" -gt 20 ]; then
    log "✅ [线程B] Level1 成功: ${count} 条评论"
    echo "1" > "$REVIEWS_LEVEL"
    echo "ok:${count}" > "$REVIEWS_DONE"
    return 0
  fi

  # Level 2: 浏览器自动化（通知 AI 主流程执行）
  log "⚠️  [线程B] Level1 不足(${count}条，exit=${apify_exit})，切换 Level 2: 浏览器自动化"
  echo "2" > "$REVIEWS_LEVEL"
  echo "need_browser:${ASIN}:${DOMAIN}:${MAX_REVIEWS}:${reviews_file}" > "${STATUS_DIR}/need_level2"

  # 等待 AI 主流程完成 Level2（最多等 3 分钟）
  local waited=0
  while [ ! -f "${STATUS_DIR}/level2.done" ] && [ $waited -lt 180 ]; do
    sleep 5
    waited=$((waited + 5))
  done

  if [ -f "${STATUS_DIR}/level2.done" ]; then
    local level2_result
    level2_result=$(cat "${STATUS_DIR}/level2.done")
    count=$(python3 -c "import json; print(len(json.load(open('$reviews_file'))))" 2>/dev/null || echo "0")

    if [ "$level2_result" = "no_next_page" ] || [ "$count" -lt 20 ]; then
      # Level 3: 切换站点
      log "⚠️  [线程B] Level2 不足(${count}条)，切换 Level 3: 站点切换"
      echo "3" > "$REVIEWS_LEVEL"
      echo "need_domain_switch:${count}" > "${STATUS_DIR}/need_level3"
      # 等待用户选择（最多等 5 分钟）
      waited=0
      while [ ! -f "${STATUS_DIR}/level3.done" ] && [ $waited -lt 300 ]; do
        sleep 5
        waited=$((waited + 5))
      done
    fi
  fi

  count=$(python3 -c "import json; print(len(json.load(open('$reviews_file'))))" 2>/dev/null || echo "0")
  log "📦 [线程B] 最终评论数: ${count}"

  if [ "$count" -eq 0 ]; then
    echo "empty" > "$REVIEWS_DONE"
  elif [ "$count" -lt 20 ]; then
    echo "limited:${count}" > "$REVIEWS_DONE"
  else
    echo "ok:${count}" > "$REVIEWS_DONE"
  fi
}

# ── 主流程：并行启动两个线程 ─────────────────────────────────────
main() {
  log "🚀 Pipeline 启动: ASIN=${ASIN} DOMAIN=${DOMAIN} MAX=${MAX_REVIEWS}"
  log "📁 报告目录: ${REPORT_DIR}"

  # 清理上次状态
  rm -f "$PRODUCT_DONE" "$REVIEWS_DONE" "$REVIEWS_LEVEL"
  rm -f "${STATUS_DIR}/need_level2" "${STATUS_DIR}/need_level3"
  rm -f "${STATUS_DIR}/level2.done" "${STATUS_DIR}/level3.done"

  # 并行启动
  thread_product &
  local pid_a=$!

  thread_reviews &
  local pid_b=$!

  log "⚙️  线程A PID: ${pid_a} | 线程B PID: ${pid_b}"

  # 等待两个线程都完成
  wait $pid_a || true
  wait $pid_b || true

  log "✅ Pipeline 完成"

  # 输出最终状态摘要
  local product_status reviews_status reviews_level
  product_status=$(cat "$PRODUCT_DONE" 2>/dev/null || echo "unknown")
  reviews_status=$(cat "$REVIEWS_DONE" 2>/dev/null || echo "unknown")
  reviews_level=$(cat "$REVIEWS_LEVEL" 2>/dev/null || echo "1")

  python3 - <<PYEOF
import json
print(json.dumps({
  "asin": "$ASIN",
  "domain": "$DOMAIN",
  "product_status": "$product_status",
  "reviews_status": "$reviews_status",
  "reviews_level_used": "$reviews_level",
  "product_file": "${REPORT_DIR}/${ASIN}-product.json",
  "reviews_file": "${REPORT_DIR}/${ASIN}-reviews-raw.json",
  "status_dir": "$STATUS_DIR"
}, ensure_ascii=False, indent=2))
PYEOF
}

main
