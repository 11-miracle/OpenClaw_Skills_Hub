#!/usr/bin/env bash
# search-amazon.sh — 关键词/ASIN -> 候选列表（按 platform/scope/top_n 路由）
#
# New usage:
#   bash search-amazon.sh <keyword_or_asin> [platform] [domain] [max] [scope]
# Backward-compatible:
#   bash search-amazon.sh <keyword_or_asin> [domain] [max]

set -euo pipefail

INPUT="${1:?需要提供关键词或 ASIN}"
ARG2="${2:-amazon.com}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTOR_MAP="${SCRIPT_DIR}/actor-map.json"

if [[ "$ARG2" == *.* ]]; then
  PLATFORM="amazon"
  DOMAIN="$ARG2"
  MAX="${3:-10}"
  SCOPE="${4:-both}"
else
  PLATFORM="$ARG2"
  DOMAIN="${3:-}"
  MAX="${4:-10}"
  SCOPE="${5:-both}"
fi

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_apify-run.sh"

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

get_platform_field() {
  local key_path="$1"
  python3 - "$ACTOR_MAP" "$PLATFORM" "$key_path" <<'PYEOF'
import json, sys
path, platform, key_path = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    data = json.load(open(path, encoding='utf-8'))
except Exception:
    data = {}
cur = data.get(platform, {})
for key in key_path.split('.'):
    if isinstance(cur, dict):
        cur = cur.get(key)
    else:
        cur = None
        break
print(cur or '')
PYEOF
}

list_platforms() {
  python3 - "$ACTOR_MAP" <<'PYEOF'
import json, sys
try:
    data = json.load(open(sys.argv[1], encoding='utf-8'))
except Exception:
    data = {}
print(', '.join(sorted(data.keys())))
PYEOF
}

if [ "$(platform_exists)" != "yes" ]; then
  echo "❌ 未配置的平台: ${PLATFORM}. 可用平台: $(list_platforms)" >&2
  exit 1
fi

case "$SCOPE" in
  bestsellers|new_releases|both) ;;
  *)
    echo "❌ invalid scope: ${SCOPE} (bestsellers|new_releases|both)" >&2
    exit 1
    ;;
esac

if [ -z "$DOMAIN" ]; then
  DOMAIN="$(get_platform_field default_domain)"
fi

KEYWORD_BS_ACTOR="$(get_platform_field search.keyword_bestsellers_actor)"
KEYWORD_NR_ACTOR="$(get_platform_field search.keyword_new_releases_actor)"
ASIN_BS_ACTOR="$(get_platform_field search.asin_bestsellers_actor)"
ASIN_NR_ACTOR="$(get_platform_field search.asin_new_releases_actor)"

if [ -z "$KEYWORD_BS_ACTOR" ] || [ -z "$KEYWORD_NR_ACTOR" ] || [ -z "$ASIN_BS_ACTOR" ] || [ -z "$ASIN_NR_ACTOR" ]; then
  echo "❌ actor-map 配置不完整: platform=${PLATFORM}" >&2
  exit 1
fi

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
is_asin() { [[ "$1" =~ ^[A-Z0-9]{10}$ ]]; }
urlencode() { python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$1"; }

extract_asins() {
  local raw_file="$1"
  local source_label="$2"
  local max_items="$3"
  python3 - "$source_label" "$max_items" <<'PYEOF' < "$raw_file"
import json, sys, re
source = sys.argv[1]
max_items = int(sys.argv[2])
try:
    items = json.load(sys.stdin)
except Exception:
    items = []

results = []
for i, item in enumerate(items[:max_items], 1):
    asin = (item.get('asin') or item.get('ASIN') or '').strip()
    if not asin:
        url = str(item.get('url') or item.get('detailPageURL') or item.get('link') or '')
        m = re.search(r'/dp/([A-Z0-9]{10})', url)
        if m:
            asin = m.group(1)
    if not asin or len(asin) != 10:
        continue
    results.append({
        'asin': asin,
        'title': str(item.get('title') or item.get('name') or item.get('productTitle') or '')[:120],
        'rank': i,
        'source': source,
        'price': str(item.get('price') or item.get('Price') or item.get('currentPrice') or ''),
        'rating': str(item.get('stars') or item.get('rating') or ''),
        'url': f'https://www.{item.get("domain", "amazon.com")}/dp/{asin}',
    })

print(json.dumps(results, ensure_ascii=False))
PYEOF
}

merge_dedupe() {
  local file1="$1"
  local file2="$2"
  python3 - <<PYEOF
import json
def safe_load(path):
    try:
        return json.load(open(path, encoding='utf-8'))
    except Exception:
        return []

list1 = safe_load('$file1')
list2 = safe_load('$file2')
seen = {}
for item in list1 + list2:
    asin = item['asin']
    if asin not in seen:
        seen[asin] = dict(item)
    else:
        existing_src = seen[asin]['source']
        new_src = item['source']
        if new_src not in existing_src:
            seen[asin]['source'] = existing_src + '+' + new_src
print(json.dumps(list(seen.values()), ensure_ascii=False, indent=2))
PYEOF
}

run_search_call() {
  local enabled="$1"
  local actor_id="$2"
  local input_json="$3"
  local out_file="$4"

  if [ "$enabled" = "yes" ]; then
    apify_run "$actor_id" "$input_json" "$MAX" 150 > "$out_file" || echo "[]" > "$out_file"
  else
    echo "[]" > "$out_file"
  fi
}

WANT_BS="no"
WANT_NR="no"
[ "$SCOPE" = "bestsellers" ] && WANT_BS="yes"
[ "$SCOPE" = "new_releases" ] && WANT_NR="yes"
[ "$SCOPE" = "both" ] && WANT_BS="yes" && WANT_NR="yes"

if is_asin "$INPUT"; then
  echo "🔍 [Search] ASIN 模式: ${INPUT} platform=${PLATFORM} scope=${SCOPE}" >&2

  HTML=$(curl -sL \
    -H "User-Agent: ${UA}" \
    -H "Accept-Language: en-US,en;q=0.9" \
    -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
    --compressed --max-time 30 \
    "https://www.${DOMAIN}/dp/${INPUT}" 2>/dev/null || echo "")

  BS_PATH=$(echo "$HTML" | grep -o 'href="/[^"]*bestsellers[^"]*"' | head -1 | cut -d'"' -f2 | sed 's/[?#].*//' || echo "")
  NR_PATH=$(echo "$HTML" | grep -o 'href="/[^"]*new-releases[^"]*"' | head -1 | cut -d'"' -f2 | sed 's/[?#].*//' || echo "")

  BESTSELLERS_URL="https://www.${DOMAIN}${BS_PATH:-/gp/bestsellers}"
  NEW_RELEASES_URL="https://www.${DOMAIN}${NR_PATH:-/gp/new-releases}"

  TMP_BS=$(mktemp)
  TMP_NR=$(mktemp)

  run_search_call "$WANT_BS" "$ASIN_BS_ACTOR" "{\"categoryUrls\":[{\"url\":\"${BESTSELLERS_URL}\"}],\"maxItems\":${MAX}}" "$TMP_BS"
  run_search_call "$WANT_NR" "$ASIN_NR_ACTOR" "{\"categoryUrls\":[{\"url\":\"${NEW_RELEASES_URL}\"}],\"maxItems\":${MAX}}" "$TMP_NR"

  TMP_BS_LIST=$(mktemp)
  TMP_NR_LIST=$(mktemp)
  extract_asins "$TMP_BS" "bestsellers" "$MAX" > "$TMP_BS_LIST"
  extract_asins "$TMP_NR" "new_releases" "$MAX" > "$TMP_NR_LIST"

  RESULT=$(merge_dedupe "$TMP_NR_LIST" "$TMP_BS_LIST")
  rm -f "$TMP_BS" "$TMP_NR" "$TMP_BS_LIST" "$TMP_NR_LIST"
else
  echo "🔍 [Search] 关键词模式: ${INPUT} platform=${PLATFORM} scope=${SCOPE}" >&2
  KW_ENC=$(urlencode "$INPUT")

  BS_URL="https://www.${DOMAIN}/s?k=${KW_ENC}&s=exact-aware-popularity-rank"
  NR_URL="https://www.${DOMAIN}/s?k=${KW_ENC}&s=date-desc-rank"

  TMP_BS=$(mktemp)
  TMP_NR=$(mktemp)

  run_search_call "$WANT_BS" "$KEYWORD_BS_ACTOR" "{\"startUrls\":[{\"url\":\"${BS_URL}\"}],\"maxItems\":${MAX}}" "$TMP_BS"
  run_search_call "$WANT_NR" "$KEYWORD_NR_ACTOR" "{\"startUrls\":[{\"url\":\"${NR_URL}\"}],\"maxItems\":${MAX}}" "$TMP_NR"

  TMP_BS_LIST=$(mktemp)
  TMP_NR_LIST=$(mktemp)
  extract_asins "$TMP_BS" "bestsellers" "$MAX" > "$TMP_BS_LIST"
  extract_asins "$TMP_NR" "new_releases" "$MAX" > "$TMP_NR_LIST"

  RESULT=$(merge_dedupe "$TMP_NR_LIST" "$TMP_BS_LIST")
  rm -f "$TMP_BS" "$TMP_NR" "$TMP_BS_LIST" "$TMP_NR_LIST"
fi

COUNT=$(echo "$RESULT" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
echo "✅ [Search] 合计 ${COUNT} 个 ASIN" >&2
echo "$RESULT"
