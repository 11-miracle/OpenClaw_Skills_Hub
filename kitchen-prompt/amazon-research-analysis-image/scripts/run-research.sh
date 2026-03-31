#!/usr/bin/env bash
# run-research.sh — scenario-driven collect orchestrator
#
# New usage:
#   bash run-research.sh --input "B0..." --platform amazon --domain amazon.com \
#     --intent standard --scope bestsellers --top-n 10 --outputs both --review-policy balanced
#
# Backward-compatible usage:
#   bash run-research.sh <keyword_or_asin> [domain] [intent] [platform] [scope] [top_n]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/_apify-run.sh"

INPUT=""
PLATFORM="amazon"
DOMAIN=""
INTENT="standard"
SCOPE="both"
TOP_N="10"
OUTPUTS="both"
REVIEW_POLICY="balanced"
MAX_REVIEWS="200"
SCENARIO_FILE=""
REQUEST_TEXT=""

usage() {
  cat <<USAGE
Usage:
  bash run-research.sh --input <keyword_or_asin> [--platform amazon] [--domain amazon.com]
                       [--intent quick|standard|deep|batch]
                       [--scope bestsellers|new_releases|both]
                       [--top-n <1..100>] [--outputs both|report|prompt]
                       [--review-policy fast|balanced|strict]
                       [--max-reviews <n>] [--scenario-file <path>] [--request-text <text>]

Backward-compatible:
  bash run-research.sh <keyword_or_asin> [domain] [intent] [platform] [scope] [top_n]
USAGE
}

is_number() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

load_scenario_file() {
  local file="$1"
  if [ ! -f "$file" ]; then
    echo "❌ scenario file not found: $file" >&2
    exit 1
  fi

  eval "$(python3 - "$file" <<'PYEOF'
import json, shlex, sys
path = sys.argv[1]
obj = json.load(open(path, encoding='utf-8'))
keys = [
    ('INPUT', 'input'),
    ('PLATFORM', 'platform'),
    ('DOMAIN', 'domain'),
    ('INTENT', 'intent'),
    ('SCOPE', 'scope'),
    ('TOP_N', 'top_n'),
    ('OUTPUTS', 'outputs'),
    ('REVIEW_POLICY', 'review_policy'),
]
for env_name, key in keys:
    if key in obj and obj[key] is not None:
        print(f"{env_name}={shlex.quote(str(obj[key]))}")
PYEOF
)"
}

parse_long_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --input) INPUT="$2"; shift 2 ;;
      --platform) PLATFORM="$2"; shift 2 ;;
      --domain) DOMAIN="$2"; shift 2 ;;
      --intent) INTENT="$2"; shift 2 ;;
      --scope) SCOPE="$2"; shift 2 ;;
      --top-n) TOP_N="$2"; shift 2 ;;
      --outputs) OUTPUTS="$2"; shift 2 ;;
      --review-policy) REVIEW_POLICY="$2"; shift 2 ;;
      --max-reviews) MAX_REVIEWS="$2"; shift 2 ;;
      --scenario-file) SCENARIO_FILE="$2"; shift 2 ;;
      --request-text) REQUEST_TEXT="$2"; shift 2 ;;
      --help|-h) usage; exit 0 ;;
      *)
        echo "❌ unknown arg: $1" >&2
        usage
        exit 1
        ;;
    esac
  done
}

if [ "$#" -eq 0 ]; then
  usage
  exit 1
fi

if [[ "${1:-}" == --* ]]; then
  parse_long_args "$@"
else
  INPUT="$1"
  DOMAIN="${2:-amazon.com}"
  INTENT="${3:-standard}"
  PLATFORM="${4:-amazon}"
  SCOPE="${5:-both}"
  TOP_N="${6:-10}"
fi

if [ -n "$SCENARIO_FILE" ]; then
  load_scenario_file "$SCENARIO_FILE"
fi

if [ -n "$REQUEST_TEXT" ]; then
  TMP_SCENARIO="$(mktemp)"
  RESOLVE_SCOPE="$SCOPE"
  if [ "$RESOLVE_SCOPE" = "both" ]; then
    RESOLVE_SCOPE="auto"
  fi
  python3 "${SCRIPT_DIR}/resolve_scenario.py" \
    --input "$INPUT" \
    --request "$REQUEST_TEXT" \
    --platform "$PLATFORM" \
    --domain "${DOMAIN}" \
    --intent "$INTENT" \
    --scope "$RESOLVE_SCOPE" \
    --top-n "$TOP_N" \
    --outputs "$OUTPUTS" \
    --review-policy "$REVIEW_POLICY" \
    --out "$TMP_SCENARIO" >/dev/null
  load_scenario_file "$TMP_SCENARIO"
  rm -f "$TMP_SCENARIO"
fi

if [ -z "$INPUT" ]; then
  echo "❌ missing input" >&2
  exit 1
fi

if [ -z "$DOMAIN" ]; then
  DOMAIN=$(python3 - "${SCRIPT_DIR}/actor-map.json" "$PLATFORM" <<'PYEOF'
import json, sys
path, platform = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(path, encoding='utf-8'))
except Exception:
    data = {}
print((data.get(platform, {}) or {}).get('default_domain', 'amazon.com'))
PYEOF
)
fi

case "$INTENT" in
  quick|standard|deep|batch) ;;
  *) echo "❌ invalid intent: $INTENT" >&2; exit 1 ;;
esac

case "$SCOPE" in
  bestsellers|new_releases|both) ;;
  *) echo "❌ invalid scope: $SCOPE" >&2; exit 1 ;;
esac

case "$OUTPUTS" in
  both|report|prompt) ;;
  *) echo "❌ invalid outputs: $OUTPUTS" >&2; exit 1 ;;
esac

case "$REVIEW_POLICY" in
  fast|balanced|strict) ;;
  *) echo "❌ invalid review-policy: $REVIEW_POLICY" >&2; exit 1 ;;
esac

if ! is_number "$TOP_N"; then
  echo "❌ top-n must be numeric" >&2
  exit 1
fi
if [ "$TOP_N" -lt 1 ] || [ "$TOP_N" -gt 100 ]; then
  echo "❌ top-n out of range: $TOP_N (1..100)" >&2
  exit 1
fi

if ! is_number "$MAX_REVIEWS"; then
  echo "❌ max-reviews must be numeric" >&2
  exit 1
fi

# ── 路径解析 ───────────────────────────────────────────────────────────────
_PATHS=$(python3 "${SCRIPT_DIR}/paths.py" 2>/dev/null)
WORKSPACE=$(echo "$_PATHS" | python3 -c "import json,sys; print(json.load(sys.stdin)['workspace'])" 2>/dev/null \
            || echo "${HOME}/.openclaw/workspace")

# ── Token 检查（首次自动保存）────────────────────────────────────────────
ensure_apify_tokens_configured || exit 1

SLUG=$(echo "$INPUT" | python3 -c "
import sys, re
s = sys.stdin.read().strip()
s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
print((s or 'empty')[:40])
")

RUN_DIR="${WORKSPACE}/amazon-research/${PLATFORM}-${SLUG}-${SCOPE}-top${TOP_N}"
PRODUCTS_DIR="${RUN_DIR}/products"
REVIEWS_DIR="${RUN_DIR}/reviews"
mkdir -p "$PRODUCTS_DIR" "$REVIEWS_DIR"

SCENARIO_JSON="${RUN_DIR}/scenario.json"
EXEC_PLAN_JSON="${RUN_DIR}/execution-plan.json"
ARTIFACTS_JSON="${RUN_DIR}/artifacts.json"

python3 - "$SCENARIO_JSON" "$INPUT" "$PLATFORM" "$DOMAIN" "$INTENT" "$SCOPE" "$TOP_N" "$OUTPUTS" "$REVIEW_POLICY" "$MAX_REVIEWS" <<'PYEOF'
import json, sys
out = sys.argv[1]
obj = {
  "input": sys.argv[2],
  "platform": sys.argv[3],
  "domain": sys.argv[4],
  "intent": sys.argv[5],
  "scope": sys.argv[6],
  "top_n": int(sys.argv[7]),
  "outputs": sys.argv[8],
  "review_policy": sys.argv[9],
  "max_reviews_cap": int(sys.argv[10]),
}
json.dump(obj, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
PYEOF

python3 - "$EXEC_PLAN_JSON" "$RUN_DIR" "$SCENARIO_JSON" <<'PYEOF'
import json, sys
out, run_dir, scenario = sys.argv[1], sys.argv[2], sys.argv[3]
plan = {
  "run_dir": run_dir,
  "scenario_file": scenario,
  "steps": [
    {"id": "step1_search", "output": f"{run_dir}/search-results.json"},
    {"id": "step2_products", "output": f"{run_dir}/products/*.json"},
    {"id": "step3_reviews", "output": f"{run_dir}/reviews/*-reviews.json"},
    {"id": "step4_summary", "output": f"{run_dir}/summary.json"}
  ]
}
json.dump(plan, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
PYEOF

START_TIME=$(date +%s)

echo ""
echo "══════════════════════════════════════════════════════"
echo "  🔬 Scenario-driven Collect"
echo "  输入:        ${INPUT}"
echo "  平台:        ${PLATFORM}"
echo "  站点:        ${DOMAIN}"
echo "  意图:        ${INTENT}"
echo "  范围:        ${SCOPE}"
echo "  TopN:        ${TOP_N}"
echo "  评论策略:    ${REVIEW_POLICY}"
echo "  输出目标:    ${OUTPUTS}"
echo "  工作目录:    ${RUN_DIR}"
echo "══════════════════════════════════════════════════════"
echo ""

SEARCH_RESULTS="${RUN_DIR}/search-results.json"

echo "【Step 1/3】搜索候选列表..."
if [ -f "$SEARCH_RESULTS" ]; then
  EXISTING=$(python3 -c "import json; print(len(json.load(open('${SEARCH_RESULTS}', encoding='utf-8'))))" 2>/dev/null || echo 0)
  echo "  ↳ search-results.json 已存在（${EXISTING} 条），跳过"
else
  bash "${SCRIPT_DIR}/search-amazon.sh" "$INPUT" "$PLATFORM" "$DOMAIN" "$TOP_N" "$SCOPE" > "$SEARCH_RESULTS"
fi
ASIN_COUNT=$(python3 -c "import json; print(len(json.load(open('${SEARCH_RESULTS}', encoding='utf-8'))))" 2>/dev/null || echo 0)
echo "  ✅ 候选数: ${ASIN_COUNT}"
echo ""

if [ "$PLATFORM" != "amazon" ]; then
  echo "❌ 当前商品详情采集仅实现 amazon 平台（platform=${PLATFORM}）" >&2
  exit 1
fi

echo "【Step 2/3】采集商品详情..."
bash "${SCRIPT_DIR}/batch-scrape-products.sh" "$SEARCH_RESULTS" "$PRODUCTS_DIR" "$DOMAIN"
echo ""

echo "【Step 3/3】采集评论（Apify-only）..."
bash "${SCRIPT_DIR}/batch-scrape-reviews.sh" "$SEARCH_RESULTS" "$REVIEWS_DIR" "$DOMAIN" "$MAX_REVIEWS" "$INTENT" "$PLATFORM" "$REVIEW_POLICY"
echo ""

echo "【汇总】生成 summary.json..."
python3 - "$SEARCH_RESULTS" "$PRODUCTS_DIR" "$REVIEWS_DIR" "$INPUT" "$DOMAIN" "$INTENT" "$PLATFORM" "$SCOPE" "$TOP_N" "$OUTPUTS" "$REVIEW_POLICY" <<'PYEOF' > "${RUN_DIR}/summary.json"
import json, os, sys
from datetime import datetime

search_results_path = sys.argv[1]
products_dir = sys.argv[2]
reviews_dir = sys.argv[3]
query = sys.argv[4]
domain = sys.argv[5]
intent = sys.argv[6]
platform = sys.argv[7]
scope = sys.argv[8]
top_n = int(sys.argv[9])
outputs = sys.argv[10]
review_policy = sys.argv[11]

try:
    search_results = json.load(open(search_results_path, encoding='utf-8'))
except Exception:
    search_results = []

summary = {
    "query": query,
    "platform": platform,
    "domain": domain,
    "intent": intent,
    "scope": scope,
    "top_n": top_n,
    "outputs": outputs,
    "review_policy": review_policy,
    "generated_at": datetime.now().isoformat(),
    "total_asins": len(search_results),
    "products": [],
}

for item in search_results:
    asin = item.get("asin", "")
    product_file = os.path.join(products_dir, f"{asin}.json")
    reviews_file = os.path.join(reviews_dir, f"{asin}-reviews.json")
    meta_file = os.path.join(reviews_dir, f"{asin}-reviews-meta.json")

    product = {}
    reviews = []
    reviews_meta = {}

    if os.path.exists(product_file):
        try:
            product = json.load(open(product_file, encoding='utf-8'))
        except Exception:
            pass
    if os.path.exists(reviews_file):
        try:
            reviews = json.load(open(reviews_file, encoding='utf-8'))
        except Exception:
            pass
    if os.path.exists(meta_file):
        try:
            reviews_meta = json.load(open(meta_file, encoding='utf-8'))
        except Exception:
            pass

    summary["products"].append(
        {
            "asin": asin,
            "rank": item.get("rank"),
            "source": item.get("source"),
            "title": product.get("title") or item.get("title", ""),
            "price": product.get("price", ""),
            "rating": product.get("rating", ""),
            "review_count": product.get("review_count", ""),
            "images_count": len(product.get("images", [])),
            "aplus_images_count": len(product.get("aplus_images", [])),
            "bullets_count": len(product.get("bullets", [])),
            "reviews_count": len(reviews),
            "reviews_status": reviews_meta.get("status", ""),
            "reviews_source": reviews_meta.get("source", ""),
            "reviews_note": reviews_meta.get("note", ""),
            "product_file": product_file,
            "reviews_file": reviews_file,
        }
    )

print(json.dumps(summary, ensure_ascii=False, indent=2))
PYEOF

PRODUCTS_DONE=$(find "$PRODUCTS_DIR" -name '*.json' | wc -l | xargs)
REVIEWS_DONE=$(find "$REVIEWS_DIR" -name '*-reviews.json' | wc -l | xargs)
REVIEWS_TOTAL=$(python3 -c "
import json, glob
total = 0
for f in glob.glob('${REVIEWS_DIR}/*-reviews.json'):
    try:
        total += len(json.load(open(f, encoding='utf-8')))
    except Exception:
        pass
print(total)
" 2>/dev/null || echo 0)

python3 - "$ARTIFACTS_JSON" "$RUN_DIR" "$SCENARIO_JSON" "$EXEC_PLAN_JSON" "$PRODUCTS_DONE" "$REVIEWS_DONE" "$REVIEWS_TOTAL" <<'PYEOF'
import json, sys
out, run_dir, scenario, plan, p_done, r_done, r_total = sys.argv[1:8]
artifacts = {
  "run_dir": run_dir,
  "scenario": scenario,
  "execution_plan": plan,
  "search_results": f"{run_dir}/search-results.json",
  "summary": f"{run_dir}/summary.json",
  "products_dir": f"{run_dir}/products",
  "reviews_dir": f"{run_dir}/reviews",
  "metrics": {
    "products_done": int(p_done),
    "reviews_files_done": int(r_done),
    "reviews_total": int(r_total)
  }
}
json.dump(artifacts, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
PYEOF

END_TIME=$(date +%s)
ELAPSED=$(( END_TIME - START_TIME ))
MINS=$(( ELAPSED / 60 ))
SECS=$(( ELAPSED % 60 ))

echo ""
echo "══════════════════════════════════════════════════════"
echo "  ✅ 采集完成！耗时: ${MINS}分${SECS}秒"
echo "  📁 数据目录: ${RUN_DIR}"
echo "  📄 场景文件: ${SCENARIO_JSON}"
echo "  📄 执行计划: ${EXEC_PLAN_JSON}"
echo "  📄 产物索引: ${ARTIFACTS_JSON}"
echo "  📋 汇总文件: ${RUN_DIR}/summary.json"
echo "══════════════════════════════════════════════════════"
echo ""

echo "$RUN_DIR"
