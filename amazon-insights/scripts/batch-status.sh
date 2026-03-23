#!/usr/bin/env bash
# batch-status.sh — 查看批量任务进度
# 用法: bash batch-status.sh

STATUS_FILE="${HOME}/.openclaw/workspace/batch/status.json"
REPORT_BASE="${HOME}/.openclaw/workspace/reports"

if [ ! -f "$STATUS_FILE" ]; then
  echo "❌ 状态文件不存在，请先运行 batch-run.sh"
  exit 1
fi

python3 - <<'PYEOF'
import json, os, sys

STATUS_FILE = os.path.expanduser("~/.openclaw/workspace/batch/status.json")
REPORT_BASE = os.path.expanduser("~/.openclaw/workspace/reports")

d = json.load(open(STATUS_FILE))
total = len(d)

counts = {}
for v in d.values():
    s = v.get('status', 'unknown')
    counts[s] = counts.get(s, 0) + 1

done       = counts.get('done', 0)
failed     = counts.get('failed', 0)
analyzing  = counts.get('pending_analysis', 0)
scraping   = counts.get('scraping_reviews', 0) + counts.get('scraping_product', 0)
pending    = counts.get('pending', 0)

print(f"\n{'='*60}")
print(f"  批量任务进度总览")
print(f"{'='*60}")
bar_done = int(done / total * 40) if total else 0
bar = '█' * bar_done + '░' * (40 - bar_done)
print(f"  [{bar}] {done}/{total}")
print(f"  ✅ 完成: {done}  🔄 分析中: {analyzing}  ⏳ 采集中: {scraping}  📋 待处理: {pending}  ❌ 失败: {failed}")
print(f"{'='*60}")

print(f"\n{'ASIN':<14} {'状态':<16} {'评论数':<8} {'商品名':<40}")
print(f"{'-'*14} {'-'*16} {'-'*8} {'-'*40}")

status_icon = {
    'done':             '✅',
    'failed':           '❌',
    'pending':          '📋',
    'pending_analysis': '🔬',
    'scraping_product': '📦',
    'scraping_reviews': '💬',
    'unknown':          '❓',
}

for asin, v in sorted(d.items()):
    st = v.get('status', 'unknown')
    icon = status_icon.get(st, '❓')
    reviews = v.get('reviews') or '-'
    # 尝试读商品名
    product_file = os.path.join(REPORT_BASE, asin, f"{asin}-product.json")
    title = '-'
    if os.path.exists(product_file):
        try:
            p = json.load(open(product_file))
            title = (p.get('title') or '-')[:38]
        except:
            pass
    print(f"  {asin:<12} {icon} {st:<14} {str(reviews):<8} {title}")

print(f"\n{'='*60}")
print(f"  报告目录: {REPORT_BASE}")
print(f"  汇总报告: {REPORT_BASE}/batch-summary.html")
print(f"{'='*60}\n")
PYEOF
