#!/usr/bin/env bash
# End-to-end orchestration: collect -> report(optional) -> prompt(optional)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

INPUT=""
DOMAIN="amazon.com"
INTENT="standard"
PLATFORM="amazon"
SCOPE="both"
TOP_N="10"
REVIEW_POLICY="balanced"
OUTPUTS="both"
FORMAT="both" # both|html|excel
SCENARIO_FILE=""
REQUEST_TEXT=""
MAX_REVIEWS="200"

usage() {
  cat <<USAGE
Usage:
  bash run-analysis-flow.sh --input <keyword_or_asin> [--domain amazon.com] [--intent standard]
                            [--platform amazon] [--scope both] [--top-n 10]
                            [--review-policy balanced] [--outputs both]
                            [--format both|html|excel]
                            [--scenario-file path] [--request-text text]

Backward-compatible positional:
  bash run-analysis-flow.sh <input> [domain] [intent] [format] [platform] [scope] [top_n] [review_policy] [outputs]
USAGE
}

parse_long_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --input) INPUT="$2"; shift 2 ;;
      --domain) DOMAIN="$2"; shift 2 ;;
      --intent) INTENT="$2"; shift 2 ;;
      --platform) PLATFORM="$2"; shift 2 ;;
      --scope) SCOPE="$2"; shift 2 ;;
      --top-n) TOP_N="$2"; shift 2 ;;
      --review-policy) REVIEW_POLICY="$2"; shift 2 ;;
      --outputs) OUTPUTS="$2"; shift 2 ;;
      --format) FORMAT="$2"; shift 2 ;;
      --scenario-file) SCENARIO_FILE="$2"; shift 2 ;;
      --request-text) REQUEST_TEXT="$2"; shift 2 ;;
      --max-reviews) MAX_REVIEWS="$2"; shift 2 ;;
      --help|-h) usage; exit 0 ;;
      *) echo "❌ unknown arg: $1" >&2; usage; exit 1 ;;
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
  FORMAT="${4:-both}"
  PLATFORM="${5:-amazon}"
  SCOPE="${6:-both}"
  TOP_N="${7:-10}"
  REVIEW_POLICY="${8:-balanced}"
  OUTPUTS="${9:-both}"
fi

if [ -z "$INPUT" ] && [ -z "$SCENARIO_FILE" ]; then
  echo "❌ missing input (or provide --scenario-file)" >&2
  exit 1
fi

if [[ "$FORMAT" != "both" && "$FORMAT" != "html" && "$FORMAT" != "excel" ]]; then
  echo "❌ invalid format: $FORMAT (both|html|excel)" >&2
  exit 1
fi

TMP_LOG="$(mktemp)"
trap 'rm -f "$TMP_LOG"' EXIT

COLLECT_ARGS=(
  --domain "$DOMAIN"
  --intent "$INTENT"
  --platform "$PLATFORM"
  --scope "$SCOPE"
  --top-n "$TOP_N"
  --outputs "$OUTPUTS"
  --review-policy "$REVIEW_POLICY"
  --max-reviews "$MAX_REVIEWS"
)

[ -n "$INPUT" ] && COLLECT_ARGS=(--input "$INPUT" "${COLLECT_ARGS[@]}")

[ -n "$SCENARIO_FILE" ] && COLLECT_ARGS+=(--scenario-file "$SCENARIO_FILE")
[ -n "$REQUEST_TEXT" ] && COLLECT_ARGS+=(--request-text "$REQUEST_TEXT")

bash "$SCRIPT_DIR/run-amazon-collect.sh" "${COLLECT_ARGS[@]}" | tee "$TMP_LOG"
RUN_DIR="$(tail -n 1 "$TMP_LOG")"

if [ -z "$RUN_DIR" ] || [ ! -d "$RUN_DIR" ]; then
  echo "❌ failed to resolve run directory" >&2
  exit 1
fi

SCENARIO_JSON="$RUN_DIR/scenario.json"
if [ -f "$SCENARIO_JSON" ]; then
  OUTPUTS=$(python3 - "$SCENARIO_JSON" <<'PYEOF'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding='utf-8'))
except Exception:
    d = {}
print(d.get('outputs', 'both'))
PYEOF
)
fi

DO_REPORT="no"
DO_PROMPT="no"
if [[ "$OUTPUTS" == "both" || "$OUTPUTS" == "report" ]]; then DO_REPORT="yes"; fi
if [[ "$OUTPUTS" == "both" || "$OUTPUTS" == "prompt" ]]; then DO_PROMPT="yes"; fi

mkdir -p "$RUN_DIR/output"

REPORT_STATUS=0
REPORT_HTML=""
REPORT_XLSX=""
if [ "$DO_REPORT" = "yes" ]; then
  REPORT_BASE="$(python3 "$SCRIPT_DIR/prepare_report_base.py" --run-dir "$RUN_DIR")"
  TS="$(date +%Y%m%d-%H%M%S)"
  REPORT_HTML="$RUN_DIR/output/report-${TS}.html"
  REPORT_XLSX="$RUN_DIR/output/report-${TS}.xlsx"

  python3 "$SCRIPT_DIR/generate_multi_asin_report.py" \
    --base-dir "$REPORT_BASE" \
    --format "$FORMAT" \
    --output "$REPORT_HTML" \
    --excel-output "$REPORT_XLSX" || REPORT_STATUS=$?
fi

PROMPT_STATUS=0
PROMPT_PATH=""
if [ "$DO_PROMPT" = "yes" ]; then
  if ! PROMPT_PATH="$(python3 "$SCRIPT_DIR/generate_image_prompt_cn.py" --run-dir "$RUN_DIR")"; then
    PROMPT_STATUS=1
  fi
fi

echo ""
echo "========== FLOW OUTPUT =========="
echo "run_dir: $RUN_DIR"
echo "outputs: $OUTPUTS"
if [ "$DO_REPORT" = "yes" ]; then
  if [ "$REPORT_STATUS" -eq 0 ]; then
    echo "report: success"
    echo "report_html: $REPORT_HTML"
    echo "report_xlsx: $REPORT_XLSX"
  else
    echo "report: failed (exit=$REPORT_STATUS)"
  fi
else
  echo "report: skipped"
fi

if [ "$DO_PROMPT" = "yes" ]; then
  if [ "$PROMPT_STATUS" -eq 0 ]; then
    echo "prompt: success"
    echo "prompt_file: $PROMPT_PATH"
  else
    echo "prompt: failed"
  fi
else
  echo "prompt: skipped"
fi
echo "================================"

echo "$RUN_DIR"
