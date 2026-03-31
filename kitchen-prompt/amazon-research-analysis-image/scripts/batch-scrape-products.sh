#!/usr/bin/env bash
# batch-scrape-products.sh — 批量爬取商品详情（curl 直接抓，不消耗 Apify 额度）
# 用法: bash batch-scrape-products.sh <search-results.json> <output_dir> [domain]
# 依赖: python3, curl

set -uo pipefail

RESULTS_JSON="${1:?需要提供 search-results.json 路径}"
OUTPUT_DIR="${2:?需要提供输出目录}"
DOMAIN="${3:-amazon.com}"

mkdir -p "${OUTPUT_DIR}"

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# 提取 ASIN 列表（换行分隔）
ASINS=$(python3 -c "
import json
data = json.load(open('${RESULTS_JSON}'))
print('\n'.join(item['asin'] for item in data if item.get('asin')))
")

TOTAL=$(echo "$ASINS" | grep -c '[A-Z0-9]' || echo 0)
echo "📦 [Products] 开始采集 ${TOTAL} 个商品详情（curl 直接抓，不消耗 Apify）..." >&2

i=0
while IFS= read -r ASIN; do
  [[ -z "$ASIN" || ! "$ASIN" =~ ^[A-Z0-9]{10}$ ]] && continue
  i=$((i + 1))
  OUT_FILE="${OUTPUT_DIR}/${ASIN}.json"

  if [ -f "$OUT_FILE" ]; then
    TITLE_EXIST=$(python3 -c "import json; print(json.load(open('${OUT_FILE}')).get('title','')[:30])" 2>/dev/null || echo "")
    echo "⏭️  [Products] ${i}/${TOTAL} ${ASIN} — 已存在（${TITLE_EXIST}），跳过" >&2
    continue
  fi

  echo "🔍 [Products] ${i}/${TOTAL} ${ASIN}" >&2

  PRODUCT_URL="https://www.${DOMAIN}/dp/${ASIN}"
  TMP_HTML=$(mktemp)

  # curl 直接抓商品页 HTML，记录 HTTP 状态码
  HTTP_CODE=$(curl -sL \
    -H "User-Agent: ${UA}" \
    -H "Accept-Language: en-US,en;q=0.9" \
    -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
    -H "Accept-Encoding: gzip, deflate, br" \
    --compressed --max-time 30 \
    -w "%{http_code}" \
    -o "$TMP_HTML" \
    "$PRODUCT_URL" 2>/dev/null || echo "000")

  if [ "$HTTP_CODE" = "000" ] || [ ! -s "$TMP_HTML" ]; then
    echo "⚠️  [Products] ${ASIN} curl 失败 (HTTP ${HTTP_CODE})，跳过" >&2
    rm -f "$TMP_HTML"
    continue
  fi

  # Python 解析 HTML → 结构化 JSON
  python3 - "$ASIN" "$DOMAIN" "$PRODUCT_URL" "$TMP_HTML" <<'PYEOF' > "$OUT_FILE"
import json, sys, re

asin      = sys.argv[1]
domain    = sys.argv[2]
url       = sys.argv[3]
html_file = sys.argv[4]

try:
    html = open(html_file, encoding='utf-8', errors='ignore').read()
except Exception:
    html = ""

def find(pattern, text, group=1, default=""):
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return m.group(group).strip() if m else default

def find_all(pattern, text):
    return [m.strip() for m in re.findall(pattern, text, re.DOTALL | re.IGNORECASE) if m.strip()]

# ── 标题 ──────────────────────────────────────────────────────────────────────
title = find(r'id="productTitle"[^>]*>\s*([^<]+)', html)
if not title:
    title = find(r'"title"\s*:\s*"([^"]{10,200})"', html)

# ── 价格 ──────────────────────────────────────────────────────────────────────
price = find(r'"priceAmount"\s*:\s*([0-9.]+)', html)
if not price:
    price = find(r'class="a-price-whole">\s*([0-9,]+)', html)
if not price:
    price = find(r'"buyingPrice"\s*:\s*"([^"]+)"', html)

# ── 评分 ──────────────────────────────────────────────────────────────────────
rating = find(r'([0-9]\.[0-9])\s*out of 5', html)
if not rating:
    rating = find(r'id="acrPopover"[^>]*title="([0-9.]+)', html)

# ── 总评论数 ──────────────────────────────────────────────────────────────────
review_count = find(r'"totalReviewCount"\s*:\s*([0-9,]+)', html)
if not review_count:
    review_count = find(r'id="acrCustomerReviewText">([^<]+)', html)

# ── 五点描述 ──────────────────────────────────────────────────────────────────
bullets_raw = find_all(r'<span class="a-list-item">\s*([^<]{15,})\s*</span>', html)
bullets = [b for b in bullets_raw if len(b) > 15][:8]
# 兜底：feature-bullets
if not bullets:
    bullets_raw2 = find_all(r'<li[^>]*>\s*<span[^>]*>\s*([^<]{20,})\s*</span>', html)
    bullets = [b for b in bullets_raw2 if len(b) > 20][:6]

# ── 主图 ──────────────────────────────────────────────────────────────────────
images = list(dict.fromkeys(
    find_all(r'"hiRes"\s*:\s*"(https://[^"]+media-amazon[^"]+)"', html)
))[:9]
if not images:
    images = list(dict.fromkeys(
        find_all(r'"large"\s*:\s*"(https://[^"]+media-amazon[^"]+)"', html)
    ))[:9]

# ── A+ 图片 ───────────────────────────────────────────────────────────────────
aplus_raw = find_all(r'(https://m\.media-amazon\.com/images/[^\s"\']+\.jpg)', html)
aplus_images = [
    u for u in dict.fromkeys(aplus_raw)
    if not any(x in u.lower() for x in ('sprite', 'icon', 'button', 'logo', 'transparent', 'pixel'))
][:6]

# ── 商品描述 ──────────────────────────────────────────────────────────────────
description = find(r'id="productDescription"[^>]*>(.*?)</div>', html, 1, "")
description = re.sub(r'<[^>]+>', ' ', description).strip()
description = re.sub(r'\s+', ' ', description)[:3000]

# ── 类目 ──────────────────────────────────────────────────────────────────────
category = find(r'"wayfairBreadcrumbs"\s*:\s*"([^"]+)"', html)
if not category:
    cat_raw = find(r'class="a-breadcrumb[^"]*"[^>]*>(.*?)</[uo]l>', html, 1, "")
    category = re.sub(r'<[^>]+>', ' ', cat_raw).strip()
    category = re.sub(r'\s+', ' ', category)[:200]

result = {
    'asin':         asin,
    'domain':       domain,
    'url':          url,
    'title':        title,
    'price':        price,
    'rating':       rating,
    'review_count': review_count,
    'bullets':      bullets,
    'description':  description,
    'images':       images,
    'aplus_images': aplus_images,
    'category':     category,
    'source':       'curl',
}

print(json.dumps(result, ensure_ascii=False, indent=2))
PYEOF

  rm -f "$TMP_HTML"

  # 验证标题是否提取成功
  TITLE_CHECK=$(python3 -c "import json; print(json.load(open('${OUT_FILE}')).get('title','')[:30])" 2>/dev/null || echo "")
  if [ -z "$TITLE_CHECK" ]; then
    echo "⚠️  [Products] ${ASIN} 标题为空，可能被反爬（数据已保存，后续分析可标注）" >&2
  else
    echo "✅ [Products] ${ASIN}: ${TITLE_CHECK}..." >&2
  fi

  sleep 1  # 礼貌延迟（比 Apify 路径短）
done <<< "$ASINS"

echo "✅ [Products] 全部完成（${i}/${TOTAL}）" >&2
