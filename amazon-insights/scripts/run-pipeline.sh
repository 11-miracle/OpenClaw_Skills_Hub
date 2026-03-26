#!/usr/bin/env bash
# run-pipeline.sh — 并行调度主脚本（v2，接入 scrape-reviews.py）
# 用法: bash run-pipeline.sh <ASIN> [domain] [max_reviews]
#
# 执行策略：
#   线程A（商品信息）和线程B（评论爬取）同时启动，互不阻塞
#   线程A完成后立即流式输出商品卡片，触发①③分析
#   线程B统一由 scrape-reviews.py 管理降级链，有明确硬出口
#   两线程都完成后输出最终 pipeline 状态 JSON
#
# 退出码:
#   0 = 全部成功
#   2 = 部分成功（商品或评论有一项降级/数据不足）
#   1 = 严重错误

set -uo pipefail

ASIN="${1:?需要提供 ASIN}"
DOMAIN="${2:-amazon.com}"
MAX_REVIEWS="${3:-}"          # 留空则由动态计算决定；明确传值则直接使用
INTENT="${4:-standard}"       # quick / standard / deep / batch

# 跨平台路径解析
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_PATHS=$(python3 "${SCRIPTS_DIR}/paths.py" "$ASIN" 2>/dev/null)
REPORT_DIR=$(echo "$_PATHS" | python3 -c "import json,sys; print(json.load(sys.stdin)['report_dir'])" 2>/dev/null \
             || echo "${HOME}/.openclaw/workspace/reports/${ASIN}")

STATUS_DIR="/tmp/pipeline-${ASIN}"
mkdir -p "$STATUS_DIR" "$REPORT_DIR"

PRODUCT_DONE="${STATUS_DIR}/product.done"
REVIEWS_DONE="${STATUS_DIR}/reviews.done"
PRODUCT_META="${STATUS_DIR}/product-meta.json"   # 线程A写入，线程B读取总评论数
PIPELINE_LOG="${STATUS_DIR}/pipeline.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$PIPELINE_LOG" >&2; }

# ── 线程A：商品信息采集 ──────────────────────────────────────────
thread_product() {
  log "▶ [线程A] 启动商品信息爬取..."
  local product_file="${REPORT_DIR}/${ASIN}-product.json"

  if bash "${SCRIPTS_DIR}/scrape-product.sh" "$ASIN" "$DOMAIN" \
       > "$product_file" 2>>"$PIPELINE_LOG"; then
    # 提取关键字段写入 product-meta.json，供线程B读取总评论数
    python3 - <<PYEOF
import json, os
try:
    p = json.load(open("$product_file"))
    raw = str(p.get("review_count") or "0")
    total = int("".join(filter(str.isdigit, raw)) or 0)
    title = p.get("title", "")[:50]
    meta  = {"total_reviews": total, "title": title, "status": "ok"}
except Exception as e:
    meta = {"total_reviews": 0, "title": "", "status": "error", "error": str(e)}
json.dump(meta, open("$PRODUCT_META", "w"), ensure_ascii=False)
print(meta.get("title", ""))
PYEOF
    local title
    title=$(python3 -c \
      "import json; print(json.load(open('$PRODUCT_META')).get('title',''))" \
      2>/dev/null || echo "")
    log "✅ [线程A] 商品信息完成: ${title}"
    echo "ok" > "$PRODUCT_DONE"
  else
    log "⚠️  [线程A] scrape-product 失败，标记 fallback（不中断流程）"
    echo '{"total_reviews":0,"status":"fallback"}' > "$PRODUCT_META"
    echo "fallback" > "$PRODUCT_DONE"
  fi
}

# ── 线程B：评论爬取（由 scrape-reviews.py 统一管理）────────────────
thread_reviews() {
  log "▶ [线程B] 启动评论爬取 (scrape-reviews.py)..."

  # 等待线程A写入 product-meta（最多 60s），拿到总评论数做动态计算
  local waited=0
  while [ ! -f "$PRODUCT_META" ] && [ $waited -lt 60 ]; do
    sleep 2; waited=$((waited+2))
  done
  local total_reviews=0
  if [ -f "$PRODUCT_META" ]; then
    total_reviews=$(python3 -c \
      "import json; print(json.load(open('$PRODUCT_META')).get('total_reviews',0))" \
      2>/dev/null || echo "0")
    log "🔢 [线程B] 总评论数=${total_reviews}，意图=${INTENT}，动态计算目标量"
  fi

  local review_output review_exit=0
  review_output=$(python3 "${SCRIPTS_DIR}/scrape-reviews.py" \
    --asin "$ASIN" --domain "$DOMAIN" \
    --total-reviews "$total_reviews" --intent "$INTENT" \
    --output "$REPORT_DIR" 2>>"$PIPELINE_LOG") || review_exit=$?

  # 检查是否需要 AI 执行浏览器操作（Level 2/3）
  local need_browser=0
  echo "$review_output" | python3 -c "
import json,sys
try:
    d = json.load(sys.stdin)
    if d.get('status') == 'need_browser':
        import os
        instr_file = '${STATUS_DIR}/need_browser.json'
        json.dump(d, open(instr_file,'w'), ensure_ascii=False, indent=2)
        print('need_browser')
    else:
        print(d.get('status','unknown'))
except:
    print('unknown')
" > "${STATUS_DIR}/review_script_status.txt" 2>/dev/null

  local script_status
  script_status=$(cat "${STATUS_DIR}/review_script_status.txt" 2>/dev/null || echo "unknown")

  if [ "$script_status" = "need_browser" ]; then
    log "🔄 [线程B] 需要浏览器操作，等待 AI 执行（最多 300s）..."
    # 通知 AI 主流程：指令文件已写入 STATUS_DIR/need_browser.json
    echo "need_browser" > "$REVIEWS_DONE"

    # 轮询等待 AI 将结果写入 reviews-meta.json（硬超时 300s）
    local waited=0
    local meta_file="${REPORT_DIR}/${ASIN}-reviews-meta.json"
    while [ $waited -lt 300 ]; do
      if [ -f "$meta_file" ]; then
        local meta_status
        meta_status=$(python3 -c "
import json
d = json.load(open('$meta_file'))
print(d.get('status','unknown'))
" 2>/dev/null || echo "unknown")
        if [ "$meta_status" != "unknown" ] && [ "$meta_status" != "pending" ]; then
          log "✅ [线程B] 浏览器操作完成: status=${meta_status}"
          break
        fi
      fi
      sleep 5
      waited=$((waited + 5))
    done

    if [ $waited -ge 300 ]; then
      log "⏰ [线程B] 浏览器等待超时（300s），使用已有数据继续"
    fi
  fi

  # 读取最终评论数量
  local count=0
  local raw_file="${REPORT_DIR}/${ASIN}-reviews-raw.json"
  if [ -f "$raw_file" ]; then
    count=$(python3 -c \
      "import json; print(len(json.load(open('$raw_file'))))" 2>/dev/null || echo "0")
  fi

  # 读取 meta 状态（scrape-reviews.py 写入）
  local meta_status="unknown"
  local meta_note=""
  local meta_file="${REPORT_DIR}/${ASIN}-reviews-meta.json"
  if [ -f "$meta_file" ]; then
    meta_status=$(python3 -c "
import json
d = json.load(open('$meta_file'))
print(d.get('status','unknown'))
" 2>/dev/null || echo "unknown")
    meta_note=$(python3 -c "
import json
d = json.load(open('$meta_file'))
print(d.get('note',''))
" 2>/dev/null || echo "")
  fi

  log "📦 [线程B] 完成: ${count} 条评论，status=${meta_status}"
  [ -n "$meta_note" ] && log "   备注: ${meta_note}"

  # 写入 reviews.done（格式：status:count）
  echo "${meta_status}:${count}" > "$REVIEWS_DONE"
}

# ── 主流程：并行启动两个线程 ─────────────────────────────────────
main() {
  log "🚀 Pipeline 启动: ASIN=${ASIN} DOMAIN=${DOMAIN} INTENT=${INTENT} MAX=${MAX_REVIEWS:-动态计算}"
  log "📁 报告目录: ${REPORT_DIR}"

  # 清理上次状态
  rm -f "$PRODUCT_DONE" "$REVIEWS_DONE" "$PRODUCT_META"
  rm -f "${STATUS_DIR}/need_browser.json" "${STATUS_DIR}/review_script_status.txt"

  # 并行启动
  thread_product &
  local pid_a=$!
  thread_reviews &
  local pid_b=$!

  log "⚙️  线程A PID: ${pid_a} | 线程B PID: ${pid_b}"

  # 等待两个线程完成
  wait $pid_a || true
  wait $pid_b || true

  log "✅ Pipeline 两线程均已完成"

  # ── 汇总最终状态 ────────────────────────────────────────────
  local product_status reviews_raw_status
  product_status=$(cat "$PRODUCT_DONE"  2>/dev/null || echo "unknown")
  reviews_raw_status=$(cat "$REVIEWS_DONE" 2>/dev/null || echo "unknown:0")

  local reviews_status reviews_count
  reviews_status=$(echo "$reviews_raw_status" | cut -d: -f1)
  reviews_count=$(echo  "$reviews_raw_status" | cut -d: -f2)

  # 读取 meta 完整信息
  local meta_note=""
  local meta_source=""
  local meta_file="${REPORT_DIR}/${ASIN}-reviews-meta.json"
  if [ -f "$meta_file" ]; then
    meta_note=$(python3 -c "
import json; d=json.load(open('$meta_file')); print(d.get('note',''))
" 2>/dev/null || echo "")
    meta_source=$(python3 -c "
import json; d=json.load(open('$meta_file')); print(d.get('source',''))
" 2>/dev/null || echo "")
  fi

  # 计算整体 pipeline 退出码
  local exit_code=0
  if [ "$product_status" = "fallback" ] || [ "$reviews_status" = "partial" ]; then
    exit_code=2
  elif [ "$reviews_status" = "insufficient" ] || [ "$reviews_status" = "failed" ]; then
    exit_code=2
  fi

  # 输出最终状态 JSON（供 AI 主流程读取，决定后续分析步骤）
  python3 - <<PYEOF
import json
result = {
  "asin":            "$ASIN",
  "domain":          "$DOMAIN",
  "product_status":  "$product_status",
  "reviews_status":  "$reviews_status",
  "reviews_count":   int("$reviews_count" or 0),
  "reviews_source":  "$meta_source",
  "reviews_note":    "$meta_note",
  "product_file":    "${REPORT_DIR}/${ASIN}-product.json",
  "reviews_file":    "${REPORT_DIR}/${ASIN}-reviews-raw.json",
  "reviews_meta":    "${REPORT_DIR}/${ASIN}-reviews-meta.json",
  "status_dir":      "$STATUS_DIR",
  "need_browser_instructions": "${STATUS_DIR}/need_browser.json" if "$reviews_status" == "need_browser" else None,
  "ready_for_analysis": "$reviews_status" not in ("failed",) and int("$reviews_count" or 0) >= 0
}
print(json.dumps(result, ensure_ascii=False, indent=2))
PYEOF

  exit $exit_code
}

main
