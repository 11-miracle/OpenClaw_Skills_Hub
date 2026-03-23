#!/usr/bin/env bash
# apify-reviews.sh — 通过 Apify 爬取亚马逊差评（3星及以下），支持多账号轮换
# 用法: bash apify-reviews.sh <ASIN> [domain] [max_reviews]
# 示例: bash apify-reviews.sh B08N5WRWNW amazon.com 200
#
# 退出码说明：
#   0 = 成功，有数据（stdout 输出 JSON 数组）
#   2 = 成功运行但返回0条数据（stdout 输出空数组 []）
#   1 = 失败（token耗尽、网络错误等）

set -uo pipefail

ASIN="${1:?需要提供 ASIN}"
DOMAIN="${2:-amazon.com}"
MAX_REVIEWS="${3:-200}"
STATE_FILE="${HOME}/.openclaw/workspace/memory/apify-token-state.json"
APIFY_API="https://api.apify.com/v2"

# ── 账号轮换：从环境变量收集所有 token ──────────────────────────
collect_tokens() {
  local tokens=()
  for i in $(seq 1 20); do
    local var="APIFY_TOKEN_${i}"
    local val="${!var:-}"
    [ -n "$val" ] && tokens+=("$val")
  done
  if [ ${#tokens[@]} -eq 0 ] && [ -n "${APIFY_TOKEN:-}" ]; then
    tokens+=("$APIFY_TOKEN")
  fi
  printf '%s\n' "${tokens[@]}"
}

get_current_index() {
  if [ -f "$STATE_FILE" ]; then
    python3 -c "import json,sys; d=json.load(open('$STATE_FILE')); print(d.get('apify_token_index',0))" 2>/dev/null || echo 0
  else
    echo 0
  fi
}

save_index() {
  local idx="$1"
  mkdir -p "$(dirname "$STATE_FILE")"
  python3 - <<EOF
import json, os
path = "$STATE_FILE"
d = {}
if os.path.exists(path):
    try:
        d = json.load(open(path))
    except:
        d = {}
d['apify_token_index'] = $idx
json.dump(d, open(path, 'w'), indent=2)
EOF
}

# ── 用指定 token 调用 Apify ────────────────────────────────────
run_apify() {
  local token="$1"
  local asin="$2"
  local domain="$3"
  local max="$4"

  # domain → country code
  local country_code
  case "$domain" in
    amazon.co.jp)   country_code="JP" ;;
    amazon.co.uk)   country_code="GB" ;;
    amazon.de)      country_code="DE" ;;
    amazon.fr)      country_code="FR" ;;
    amazon.ca)      country_code="CA" ;;
    amazon.com.mx)  country_code="MX" ;;
    amazon.com.br)  country_code="BR" ;;
    amazon.es)      country_code="ES" ;;
    amazon.it)      country_code="IT" ;;
    amazon.in)      country_code="IN" ;;
    amazon.com.au)  country_code="AU" ;;
    amazon.nl)      country_code="NL" ;;
    amazon.se)      country_code="SE" ;;
    amazon.pl)      country_code="PL" ;;
    amazon.sa)      country_code="SA" ;;
    amazon.ae)      country_code="AE" ;;
    amazon.sg)      country_code="SG" ;;
    *)              country_code="US" ;;
  esac

  echo "🚀 [Apify] 启动 Actor (delicious_zebu)..." >&2

  # 异步启动，不等待（waitForFinish=0），立即拿 run_id
  local run_resp
  run_resp=$(curl -sf -X POST \
    "${APIFY_API}/acts/delicious_zebu~amazon-reviews-scraper-with-advanced-filters/runs?waitForFinish=0" \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    -d "{
      \"ASIN_or_URL\": [\"${asin}\"],
      \"country\": \"${country_code}\",
      \"max_reviews\": ${max},
      \"filter_by_ratings\": [\"1 star only\", \"2 star only\", \"3 star only\"],
      \"sort_reviews_by\": [\"Most recent\"],
      \"unique_only\": true,
      \"filter_by_verified_purchase_only\": [\"All reviews\"],
      \"filter_by_mediaType\": [\"Text, image, video\", \"Text only\"]
    }" 2>&1) || {
      if echo "$run_resp" | grep -q "429\|rateLimitExceeded\|monthlyUsageExceeded\|actor-is-not-rented"; then
        echo "RATE_LIMITED" >&2 && return 2
      fi
      echo "ERROR: $run_resp" >&2 && return 1
    }

  local run_id run_status dataset_id
  run_id=$(echo "$run_resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['id'])" 2>/dev/null || echo "")
  run_status=$(echo "$run_resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['status'])" 2>/dev/null || echo "")
  dataset_id=$(echo "$run_resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['defaultDatasetId'])" 2>/dev/null || echo "")

  if [ -z "$run_id" ]; then
    echo "ERROR: 无法获取 run_id，响应: ${run_resp:0:200}" >&2
    return 1
  fi

  echo "📋 [Apify] Run ID: ${run_id} | 初始状态: ${run_status}" >&2

  # 轮询，硬上限 90 秒
  local max_wait=90
  local waited=0
  while [ "$run_status" != "SUCCEEDED" ] && [ "$run_status" != "FAILED" ] && \
        [ "$run_status" != "ABORTED" ] && [ "$run_status" != "TIMED-OUT" ]; do
    sleep 10
    waited=$((waited + 10))
    if [ $waited -ge $max_wait ]; then
      echo "TIMEOUT_90S" >&2
      return 3
    fi
    local poll_resp
    poll_resp=$(curl -sf "${APIFY_API}/actor-runs/${run_id}?waitForFinish=10" \
      -H "Authorization: Bearer ${token}" 2>/dev/null || echo "{}")
    run_status=$(echo "$poll_resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('status',''))" 2>/dev/null || echo "")
    dataset_id=$(echo "$poll_resp" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('defaultDatasetId','$dataset_id'))" 2>/dev/null || echo "$dataset_id")
    echo "⏳ [Apify] ${waited}s - ${run_status}" >&2
  done

  if [ "$run_status" != "SUCCEEDED" ]; then
    echo "ERROR: Actor 运行失败，状态: ${run_status}" >&2
    return 1
  fi

  echo "✅ [Apify] 完成，获取数据..." >&2

  local result
  result=$(curl -sf "${APIFY_API}/datasets/${dataset_id}/items?clean=true&limit=${max}" \
    -H "Authorization: Bearer ${token}")

  local count
  count=$(echo "$result" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
  echo "📦 [Apify] 获取 ${count} 条评论" >&2

  if [ "$count" = "0" ]; then
    echo "[]"
    return 2
  fi

  echo "$result"
  return 0
}

# ── 主逻辑 ────────────────────────────────────────────────────
main() {
  local tokens_raw
  tokens_raw=$(collect_tokens)
  local TOKENS=()
  while IFS= read -r line; do
    [ -n "$line" ] && TOKENS+=("$line")
  done <<< "$tokens_raw"
  local total=${#TOKENS[@]}

  if [ $total -eq 0 ]; then
    echo '[]' 
    echo '{"error": "no_tokens"}' >&2
    exit 2
  fi

  local start_idx
  start_idx=$(get_current_index)
  local idx=$start_idx

  for attempt in $(seq 1 $total); do
    local token="${TOKENS[$idx]}"
    echo "🔑 [Apify] 使用账号$((idx+1)) (共 ${total} 个)" >&2

    local result exit_code
    result=$(run_apify "$token" "$ASIN" "$DOMAIN" "$MAX_REVIEWS")
    exit_code=$?

    case $exit_code in
      0)
        save_index $idx
        echo "$result"
        exit 0
        ;;
      2)
        # 0条数据，切换账号重试
        echo "⚠️  [Apify] 账号$((idx+1)) 返回0条，切换账号..." >&2
        idx=$(( (idx + 1) % total ))
        save_index $idx
        ;;
      3)
        # 90s 超时
        echo "⏰ [Apify] 90s 超时，退出等待" >&2
        echo "[]"
        exit 3
        ;;
      *)
        echo "$result" >&2
        idx=$(( (idx + 1) % total ))
        save_index $idx
        ;;
    esac
  done

  echo "[]"
  echo '{"error": "all_tokens_exhausted"}' >&2
  exit 2
}

main
