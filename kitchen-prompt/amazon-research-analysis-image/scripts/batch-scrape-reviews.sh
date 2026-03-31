#!/usr/bin/env bash
# batch-scrape-reviews.sh — 批量采集评论（Apify-only）
# 用法:
#   bash batch-scrape-reviews.sh <search-results.json> <output_dir> [domain] [max_per_asin] [intent] [platform] [review_policy]

set -euo pipefail

RESULTS_JSON="${1:?需要提供 search-results.json 路径}"
OUTPUT_DIR="${2:?需要提供输出目录}"
DOMAIN="${3:-amazon.com}"
MAX_PER_ASIN="${4:-200}"
INTENT="${5:-standard}"
PLATFORM="${6:-amazon}"
REVIEW_POLICY="${7:-balanced}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "${OUTPUT_DIR}"

ASINS=$(python3 -c "
import json
try:
    data = json.load(open('${RESULTS_JSON}', encoding='utf-8'))
except Exception:
    data = []
print('\\n'.join(item.get('asin','') for item in data if item.get('asin')))
")

TOTAL=$(echo "$ASINS" | grep -c '[A-Z0-9]' || echo 0)
echo "💬 [Reviews] 开始采集 ${TOTAL} 个商品评论（平台=${PLATFORM}，意图=${INTENT}，策略=${REVIEW_POLICY}）..." >&2

i=0
while IFS= read -r ASIN; do
  [[ -z "$ASIN" || ! "$ASIN" =~ ^[A-Z0-9]{10}$ ]] && continue
  i=$((i + 1))
  OUT_FILE="${OUTPUT_DIR}/${ASIN}-reviews.json"

  if [ -f "$OUT_FILE" ]; then
    COUNT_EXIST=$(python3 -c "import json; print(len(json.load(open('${OUT_FILE}', encoding='utf-8'))))" 2>/dev/null || echo "?")
    echo "⏭️  [Reviews] ${i}/${TOTAL} ${ASIN} — 已存在（${COUNT_EXIST}条），跳过" >&2
    continue
  fi

  echo "💬 [Reviews] ${i}/${TOTAL} ${ASIN}" >&2

  python3 "${SCRIPT_DIR}/scrape-reviews-batch.py" \
    --asin "$ASIN" \
    --domain "$DOMAIN" \
    --platform "$PLATFORM" \
    --intent "$INTENT" \
    --review-policy "$REVIEW_POLICY" \
    --max "$MAX_PER_ASIN" \
    --output "$OUTPUT_DIR" \
    2>&1 | tee /dev/stderr || true

  if [ -f "$OUT_FILE" ]; then
    COUNT=$(python3 -c "import json; print(len(json.load(open('${OUT_FILE}', encoding='utf-8'))))" 2>/dev/null || echo 0)
    META_FILE="${OUTPUT_DIR}/${ASIN}-reviews-meta.json"
    if [ -f "$META_FILE" ]; then
      META_STATUS=$(python3 -c "import json; print(json.load(open('${META_FILE}', encoding='utf-8')).get('status',''))" 2>/dev/null || echo "")
      META_SOURCE=$(python3 -c "import json; print(json.load(open('${META_FILE}', encoding='utf-8')).get('source',''))" 2>/dev/null || echo "")
      echo "✅ [Reviews] ${ASIN}: ${COUNT} 条 [status=${META_STATUS}, source=${META_SOURCE}]" >&2
    else
      echo "✅ [Reviews] ${ASIN}: ${COUNT} 条" >&2
    fi
  else
    echo "⚠️  [Reviews] ${ASIN}: 未生成输出文件" >&2
  fi

  sleep 1
done <<< "$ASINS"

echo "✅ [Reviews] 全部完成（${i}/${TOTAL}）" >&2
