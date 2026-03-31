#!/usr/bin/env bash
# apify-reviews-batch.sh — 通过 Apify Actor 爬取评论（支持 platform 路由）
# 用法: bash apify-reviews-batch.sh <ASIN> [domain] [max_reviews] [actor_id] [platform]

set -euo pipefail

ASIN="${1:?需要提供 ASIN}"
DOMAIN="${2:-amazon.com}"
MAX_REVIEWS="${3:-200}"
ACTOR_ID="${4:-}"
PLATFORM="${5:-amazon}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTOR_MAP="${SCRIPT_DIR}/actor-map.json"

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_apify-run.sh"

resolve_primary_review_actor() {
  python3 - "$ACTOR_MAP" "$PLATFORM" <<'PYEOF'
import json, sys
path, platform = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(path, encoding='utf-8'))
except Exception:
    data = {}
print((data.get(platform, {}).get('reviews', {}) or {}).get('primary_actor', ''))
PYEOF
}

platform_exists() {
  python3 - "$ACTOR_MAP" "$PLATFORM" <<'PYEOF'
import json, sys
path, platform = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(path, encoding='utf-8'))
except Exception:
    data = {}
print('yes' if platform in data else 'no')
PYEOF
}

if [ "$(platform_exists)" != "yes" ]; then
  echo "[]"
  echo "❌ 平台未配置: ${PLATFORM}" >&2
  exit 1
fi

if [ -z "$ACTOR_ID" ]; then
  ACTOR_ID="$(resolve_primary_review_actor)"
fi

if [ -z "$ACTOR_ID" ]; then
  echo "[]"
  echo "❌ reviews actor 未配置: platform=${PLATFORM}" >&2
  exit 1
fi

domain_to_country() {
  case "$1" in
    amazon.co.jp)   echo "JP" ;;
    amazon.co.uk)   echo "GB" ;;
    amazon.de)      echo "DE" ;;
    amazon.fr)      echo "FR" ;;
    amazon.ca)      echo "CA" ;;
    amazon.com.mx)  echo "MX" ;;
    amazon.com.br)  echo "BR" ;;
    amazon.es)      echo "ES" ;;
    amazon.it)      echo "IT" ;;
    amazon.in)      echo "IN" ;;
    amazon.com.au)  echo "AU" ;;
    amazon.nl)      echo "NL" ;;
    amazon.se)      echo "SE" ;;
    amazon.pl)      echo "PL" ;;
    amazon.sa)      echo "SA" ;;
    amazon.ae)      echo "AE" ;;
    amazon.sg)      echo "SG" ;;
    *)              echo "US" ;;
  esac
}

COUNTRY_CODE="$(domain_to_country "$DOMAIN")"

if [ "$PLATFORM" = "amazon" ]; then
  INPUT_JSON=$(cat <<JSON
{
  "ASIN_or_URL": ["${ASIN}"],
  "country": "${COUNTRY_CODE}",
  "max_reviews": ${MAX_REVIEWS},
  "filter_by_ratings": ["1 star only", "2 star only", "3 star only"],
  "sort_reviews_by": ["Most recent"],
  "unique_only": true,
  "filter_by_verified_purchase_only": ["All reviews"],
  "filter_by_mediaType": ["Text, image, video", "Text only"]
}
JSON
)
else
  echo "[]"
  echo "❌ 当前脚本仅内置 amazon 评论输入模板，platform=${PLATFORM} 需自定义" >&2
  exit 1
fi

RESULT=$(apify_run "$ACTOR_ID" "$INPUT_JSON" "$MAX_REVIEWS" 90) || EXIT_CODE=$?
EXIT_CODE=${EXIT_CODE:-0}

if [ "$EXIT_CODE" -ne 0 ]; then
  echo "[]"
  exit "$EXIT_CODE"
fi

COUNT=$(echo "$RESULT" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
if [ "$COUNT" = "0" ]; then
  echo "[]"
  exit 2
fi

echo "$RESULT"
exit 0
