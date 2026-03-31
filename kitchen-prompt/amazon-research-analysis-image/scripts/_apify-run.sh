#!/usr/bin/env bash
# _apify-run.sh — Apify 调用共享函数（source this, do not run directly）
#
# 提供:
#   ensure_apify_tokens_configured
#   apify_run <actor_id> <input_json> [max_items=100] [timeout_s=90]

APIFY_API="https://api.apify.com/v2"
_APIFY_STATE_FILE="${HOME}/.openclaw/workspace/memory/apify-token-state.json"
_APIFY_TOKEN_ENV_FILE="${HOME}/.openclaw/workspace/memory/apify-token.env"

# ── Token 管理 ───────────────────────────────────────────────────────────────

_load_persisted_tokens() {
  if [ -f "${_APIFY_TOKEN_ENV_FILE}" ]; then
    # shellcheck source=/dev/null
    source "${_APIFY_TOKEN_ENV_FILE}" 2>/dev/null || true
  fi
}

_collect_tokens() {
  _load_persisted_tokens

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

_count_tokens() {
  local tokens_raw
  tokens_raw=$(_collect_tokens)
  local count=0
  while IFS= read -r line; do
    [ -n "$line" ] && count=$((count + 1))
  done <<< "$tokens_raw"
  echo "$count"
}

_persist_single_token() {
  local token="$1"
  mkdir -p "$(dirname "${_APIFY_TOKEN_ENV_FILE}")"
  umask 077
  cat > "${_APIFY_TOKEN_ENV_FILE}" <<EOT
APIFY_TOKEN="${token}"
EOT
  chmod 600 "${_APIFY_TOKEN_ENV_FILE}" 2>/dev/null || true
}

ensure_apify_tokens_configured() {
  local count
  count=$(_count_tokens)
  if [ "$count" -gt 0 ]; then
    return 0
  fi

  echo "" >&2
  echo "┌─────────────────────────────────────────────────────┐" >&2
  echo "│  🔑  需要 Apify API Token 才能开始采集              │" >&2
  echo "│  获取地址: https://console.apify.com/settings/      │" >&2
  echo "│            integrations                             │" >&2
  echo "│                                                     │" >&2
  echo "│  首次输入后将保存到本机 memory/apify-token.env      │" >&2
  echo "└─────────────────────────────────────────────────────┘" >&2
  echo "" >&2

  if [ ! -t 0 ]; then
    echo "❌ 未检测到 APIFY_TOKEN，且当前为非交互环境。请先设置环境变量或 token 文件。" >&2
    return 1
  fi

  local token_input
  read -r -p "请输入你的 APIFY_TOKEN: " token_input
  if [ -z "$token_input" ]; then
    echo "❌ 未输入 Token，退出" >&2
    return 1
  fi

  export APIFY_TOKEN="$token_input"
  _persist_single_token "$token_input"

  echo "✅ Token 已保存：${_APIFY_TOKEN_ENV_FILE}" >&2
  return 0
}

_get_token_index() {
  python3 -c "
import json, os
f = '${_APIFY_STATE_FILE}'
d = json.load(open(f)) if os.path.exists(f) else {}
print(d.get('apify_token_index', 0))
" 2>/dev/null || echo 0
}

_save_token_index() {
  local idx="$1"
  mkdir -p "$(dirname "${_APIFY_STATE_FILE}")"
  python3 - <<EOF2
import json, os
path = "${_APIFY_STATE_FILE}"
d = json.load(open(path)) if os.path.exists(path) else {}
d['apify_token_index'] = ${idx}
json.dump(d, open(path, 'w'), indent=2)
EOF2
}

_mark_apify_exhausted() {
  mkdir -p "$(dirname "${_APIFY_STATE_FILE}")"
  python3 - <<EOF2
import json, os, time
path = "${_APIFY_STATE_FILE}"
d = json.load(open(path)) if os.path.exists(path) else {}
d['exhausted_at'] = time.time()
json.dump(d, open(path, 'w'), indent=2)
EOF2
  echo "⚠️  [Apify] 所有 token 已耗尽，记录冷却时间（4h 后自动恢复）" >&2
}

_check_apify_cooldown() {
  python3 -c "
import json, os, time
f = '${_APIFY_STATE_FILE}'
d = json.load(open(f)) if os.path.exists(f) else {}
ex = d.get('exhausted_at', 0)
hrs = (time.time() - ex) / 3600
print('cooldown' if hrs < 4 else 'available')
" 2>/dev/null || echo "available"
}

# ── 内部：单次 token 调用 ────────────────────────────────────────────────────

_apify_run_with_token() {
  local token="$1"
  local actor_id="$2"
  local input_json="$3"
  local max_items="$4"
  local timeout="$5"

  local run_resp
  run_resp=$(curl -sf -X POST \
    "${APIFY_API}/acts/${actor_id}/runs?waitForFinish=30" \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    -d "$input_json" 2>&1) || {
    if echo "$run_resp" | grep -qi "429\|rateLimitExceeded\|monthlyUsageExceeded\|actor-is-not-rented"; then
      return 2
    fi
    echo "❌ [Apify] 启动失败: ${run_resp:0:200}" >&2
    return 1
  }

  local run_id status dataset_id
  run_id=$(echo "$run_resp"     | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['id'])"                2>/dev/null || echo "")
  status=$(echo "$run_resp"     | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['status'])"            2>/dev/null || echo "")
  dataset_id=$(echo "$run_resp" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['defaultDatasetId'])"  2>/dev/null || echo "")

  if [ -z "$run_id" ]; then
    echo "❌ [Apify] 无法获取 run_id，响应: ${run_resp:0:300}" >&2
    return 1
  fi

  echo "📋 [Apify] RunID=${run_id} Status=${status}" >&2

  local waited=0
  while [[ "$status" != "SUCCEEDED" && "$status" != "FAILED" && \
           "$status" != "ABORTED"   && "$status" != "TIMED-OUT" ]]; do
    sleep 10
    waited=$((waited + 10))
    if [ $waited -ge $timeout ]; then
      echo "⏰ [Apify] 轮询超时 ${timeout}s" >&2
      return 3
    fi

    local poll
    poll=$(curl -sf "${APIFY_API}/actor-runs/${run_id}?waitForFinish=10" \
      -H "Authorization: Bearer ${token}" 2>/dev/null || echo "{}")
    status=$(echo "$poll"     | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('status',''))" 2>/dev/null || echo "")
    dataset_id=$(echo "$poll" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('defaultDatasetId','${dataset_id}'))" 2>/dev/null || echo "${dataset_id}")
    echo "⏳ [Apify] ${waited}s — ${status}" >&2
  done

  if [[ "$status" != "SUCCEEDED" ]]; then
    echo "❌ [Apify] Actor 失败，status=${status}" >&2
    return 1
  fi

  local result
  result=$(curl -sf \
    "${APIFY_API}/datasets/${dataset_id}/items?clean=true&limit=${max_items}" \
    -H "Authorization: Bearer ${token}") || {
    echo "❌ [Apify] 拉取结果失败" >&2
    return 1
  }

  echo "$result"
  return 0
}

# ── 公开接口：apify_run ──────────────────────────────────────────────────────

apify_run() {
  local actor_id="$1"
  local input_json="$2"
  local max_items="${3:-100}"
  local timeout="${4:-90}"

  ensure_apify_tokens_configured || return 1

  local cooldown_status
  cooldown_status=$(_check_apify_cooldown)
  if [ "$cooldown_status" = "cooldown" ]; then
    echo "❄️  [Apify] Token 冷却中（4h 内），跳过 Apify" >&2
    return 1
  fi

  local tokens_raw
  tokens_raw=$(_collect_tokens)
  local TOKENS=()
  while IFS= read -r line; do
    [ -n "$line" ] && TOKENS+=("$line")
  done <<< "$tokens_raw"
  local total=${#TOKENS[@]}

  if [ $total -eq 0 ]; then
    echo "❌ [Apify] 未配置任何 APIFY_TOKEN（或 APIFY_TOKEN_1~20）" >&2
    return 1
  fi

  local start_idx
  start_idx=$(_get_token_index)
  local idx=$(( start_idx % total ))

  for attempt in $(seq 1 $total); do
    local token="${TOKENS[$idx]}"
    echo "🔑 [Apify] 账号$((idx+1))/${total}，启动 ${actor_id}..." >&2

    local result exit_code=0
    result=$(_apify_run_with_token "$token" "$actor_id" "$input_json" "$max_items" "$timeout") || exit_code=$?

    case $exit_code in
      0)
        _save_token_index $idx
        echo "$result"
        return 0
        ;;
      3)
        echo "⏰ [Apify] 超时 ${timeout}s，不重试" >&2
        return 3
        ;;
      2)
        echo "⚠️  [Apify] 账号$((idx+1)) 限流，切换下一账号..." >&2
        idx=$(( (idx + 1) % total ))
        _save_token_index $idx
        ;;
      *)
        idx=$(( (idx + 1) % total ))
        _save_token_index $idx
        ;;
    esac
  done

  _mark_apify_exhausted
  return 1
}
