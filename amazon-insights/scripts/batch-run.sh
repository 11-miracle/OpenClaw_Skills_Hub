#!/usr/bin/env bash
# batch-run.sh — 批量队列调度，支持断点续跑
# 用法: bash batch-run.sh [queue_file] [max_concurrent]
# 示例: bash batch-run.sh ~/.openclaw/workspace/batch/queue.txt 1

set -uo pipefail

QUEUE_FILE="${1:-${HOME}/.openclaw/workspace/batch/queue.txt}"
MAX_CONCURRENT="${2:-1}"   # 评论爬取串行，默认1
BATCH_DIR="${HOME}/.openclaw/workspace/batch"
STATUS_FILE="${BATCH_DIR}/status.json"
REPORT_BASE="${HOME}/.openclaw/workspace/reports"
SKILL_SCRIPTS="${HOME}/openclaw/skills/amazon-insights/scripts"
LOG_FILE="${BATCH_DIR}/batch-$(date +%Y%m%d-%H%M%S).log"

mkdir -p "$BATCH_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# ── 初始化 status.json ────────────────────────────────────────
init_status() {
  if [ ! -f "$STATUS_FILE" ]; then
    echo '{}' > "$STATUS_FILE"
  fi
  # 读取队列，新增 pending 条目
  while IFS= read -r line; do
    asin=$(echo "$line" | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]')
    [ -z "$asin" ] && continue
    [[ "$asin" == \#* ]] && continue
    # 如果还没有记录，初始化为 pending
    exists=$(python3 -c "
import json,sys
d=json.load(open('$STATUS_FILE'))
print('yes' if '$asin' in d else 'no')
" 2>/dev/null || echo "no")
    if [ "$exists" = "no" ]; then
      python3 - <<PYEOF
import json,os
path='$STATUS_FILE'
d=json.load(open(path)) if os.path.exists(path) else {}
d['$asin']={'status':'pending','product':None,'reviews':None,'report':None,'error':None,'ts_start':None,'ts_done':None}
json.dump(d,open(path,'w'),ensure_ascii=False,indent=2)
PYEOF
    fi
  done < "$QUEUE_FILE"
}

# ── 更新单个 ASIN 状态 ─────────────────────────────────────────
update_status() {
  local asin="$1" field="$2" value="$3"
  python3 - <<PYEOF
import json,os
path='$STATUS_FILE'
d=json.load(open(path)) if os.path.exists(path) else {}
if '$asin' not in d:
    d['$asin']={}
d['$asin']['$field']=$value
json.dump(d,open(path,'w'),ensure_ascii=False,indent=2)
PYEOF
}

# ── 获取待处理列表 ─────────────────────────────────────────────
get_pending() {
  python3 - <<PYEOF
import json,os
path='$STATUS_FILE'
d=json.load(open(path)) if os.path.exists(path) else {}
pending=[k for k,v in d.items() if v.get('status') in ('pending','failed_retryable')]
print('\n'.join(pending))
PYEOF
}

# ── 处理单个 ASIN ──────────────────────────────────────────────
process_asin() {
  local asin="$1"
  local report_dir="${REPORT_BASE}/${asin}"
  mkdir -p "$report_dir"

  log "▶ 开始处理: ${asin}"
  update_status "$asin" "status" "'scraping_product'"
  update_status "$asin" "ts_start" "\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\""

  # Step 1: 爬取商品信息
  log "  [1/3] 商品信息爬取..."
  local product_file="${report_dir}/${asin}-product.json"
  if bash "${SKILL_SCRIPTS}/scrape-product.sh" "$asin" "amazon.com" \
       > "$product_file" 2>>"$LOG_FILE"; then
    local title
    title=$(python3 -c "import json; d=json.load(open('$product_file')); print(d.get('title','N/A')[:50])" 2>/dev/null || echo "N/A")
    log "  ✅ 商品信息: ${title}"
    update_status "$asin" "product" "'ok'"
  else
    log "  ⚠️  商品信息爬取失败，继续评论爬取"
    update_status "$asin" "product" "'failed'"
  fi

  # Step 2: 评论爬取（AI 主流程执行浏览器自动化，此处记录状态）
  update_status "$asin" "status" "'scraping_reviews'"
  log "  [2/3] 评论爬取（需 AI 执行浏览器自动化）..."

  # 写入待爬取指令文件，供 AI 主流程轮询
  local review_task="${BATCH_DIR}/review-task-${asin}.json"
  python3 -c "
import json
task = {
    'asin': '$asin',
    'domain': 'amazon.com',
    'min_reviews': 100,
    'max_reviews': 1000,
    'out_file': '${report_dir}/${asin}-reviews-raw.json',
    'status': 'pending'
}
json.dump(task, open('$review_task','w'), ensure_ascii=False, indent=2)
print('review task created')
"
  # 等待 AI 完成评论爬取（最多等 10 分钟）
  local waited=0
  local review_status="pending"
  while [ "$review_status" = "pending" ] && [ $waited -lt 600 ]; do
    sleep 10
    waited=$((waited+10))
    review_status=$(python3 -c "
import json,os
t=json.load(open('$review_task')) if os.path.exists('$review_task') else {}
print(t.get('status','pending'))
" 2>/dev/null || echo "pending")
  done

  local review_count=0
  local review_file="${report_dir}/${asin}-reviews-raw.json"
  if [ -f "$review_file" ]; then
    review_count=$(python3 -c "import json; print(len(json.load(open('$review_file'))))" 2>/dev/null || echo 0)
  fi
  log "  ✅ 评论获取: ${review_count} 条"
  update_status "$asin" "reviews" "$review_count"

  # Step 3: 标记等待分析
  update_status "$asin" "status" "'pending_analysis'"
  log "  [3/3] 等待 AI 分析生成报告..."

  log "✅ ${asin} 采集完成，等待分析"
}

# ── 主流程 ─────────────────────────────────────────────────────
main() {
  if [ ! -f "$QUEUE_FILE" ]; then
    log "❌ 队列文件不存在: ${QUEUE_FILE}"
    log "请创建文件，每行一个 ASIN："
    log "  echo 'B07Y5GHJSX' >> ${QUEUE_FILE}"
    exit 1
  fi

  log "🚀 批量任务启动"
  log "   队列文件: ${QUEUE_FILE}"
  log "   状态文件: ${STATUS_FILE}"
  log "   日志文件: ${LOG_FILE}"

  init_status

  local total
  total=$(grep -c -v '^\s*#\|^\s*$' "$QUEUE_FILE" 2>/dev/null || echo 0)
  log "   总计 ASIN: ${total}"

  local pending_list
  pending_list=$(get_pending)
  local pending_count
  pending_count=$(echo "$pending_list" | grep -c . 2>/dev/null || echo 0)
  log "   待处理: ${pending_count}"

  if [ "$pending_count" -eq 0 ]; then
    log "✅ 所有 ASIN 已处理完毕"
    exit 0
  fi

  local done_count=0
  while IFS= read -r asin; do
    [ -z "$asin" ] && continue
    process_asin "$asin"
    done_count=$((done_count+1))
    log "📊 进度: ${done_count}/${pending_count}"
  done <<< "$pending_list"

  log "🏁 批量采集完成，共处理 ${done_count} 个 ASIN"
  log "   运行: bash ${SKILL_SCRIPTS}/batch-status.sh 查看状态"
}

main
