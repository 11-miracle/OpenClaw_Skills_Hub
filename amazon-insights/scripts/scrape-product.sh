#!/usr/bin/env bash
# scrape-product.sh — 直接爬取亚马逊商品基础信息（无需登录）
# 用法: bash scrape-product.sh <ASIN> [domain]
# 示例: bash scrape-product.sh B08N5WRWNW amazon.com

set -euo pipefail

ASIN="${1:?需要提供 ASIN}"
DOMAIN="${2:-amazon.com}"
URL="https://www.${DOMAIN}/dp/${ASIN}"

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

echo "🔍 正在爬取: ${URL}" >&2

HTML=$(curl -sL \
  -H "User-Agent: ${UA}" \
  -H "Accept-Language: en-US,en;q=0.9" \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
  --compressed \
  --max-time 30 \
  "${URL}")

if [ -z "$HTML" ]; then
  echo '{"error": "empty_response"}' && exit 1
fi

# 提取标题
TITLE=$(echo "$HTML" | grep -o '<span id="productTitle"[^>]*>[^<]*' | sed 's/<[^>]*>//g' | xargs 2>/dev/null || echo "")

# 提取价格（多种格式兼容）
PRICE=$(echo "$HTML" | grep -o '"priceAmount":[0-9.]*' | head -1 | cut -d: -f2 || \
        echo "$HTML" | grep -o 'class="a-price-whole">[0-9,]*' | head -1 | sed 's/.*>//' || echo "")

# 提取评分
RATING=$(echo "$HTML" | grep -o '[0-9]\.[0-9] out of 5' | head -1 | cut -d' ' -f1 || echo "")

# 提取评论总数
REVIEW_COUNT=$(echo "$HTML" | grep -o '"totalReviewCount":[0-9]*' | head -1 | cut -d: -f2 || \
               echo "$HTML" | grep -o 'id="acrCustomerReviewText">[^<]*' | sed 's/.*>//;s/ rating.*//' | xargs || echo "")

# 提取五点描述
BULLETS=$(echo "$HTML" | grep -o '<span class="a-list-item">[^<]*' | sed 's/<[^>]*>//g' | head -10 | \
          awk 'NF>3' | head -5 | jq -R -s 'split("\n") | map(select(length>0))' 2>/dev/null || echo "[]")

# 提取商品主图（最多9张）
IMAGES=$(echo "$HTML" | grep -o '"hiRes":"https://[^"]*"' | cut -d'"' -f4 | sort -u | head -9 | \
         jq -R -s 'split("\n") | map(select(length>0))' 2>/dev/null || echo "[]")

# 提取A+详情图（前5张）
APLUS_IMAGES=$(echo "$HTML" | grep -o 'https://m\.media-amazon\.com/images/[^"'"'"']*\.jpg' | \
               grep -v 'sprite\|icon\|button\|logo' | sort -u | head -5 | \
               jq -R -s 'split("\n") | map(select(length>0))' 2>/dev/null || echo "[]")

# 提取商品描述
DESCRIPTION=$(echo "$HTML" | grep -o '<div id="productDescription"[^>]*>.*</div>' | \
              sed 's/<[^>]*>//g' | xargs 2>/dev/null | head -c 2000 || echo "")

# 输出 JSON
jq -n \
  --arg asin "$ASIN" \
  --arg domain "$DOMAIN" \
  --arg url "$URL" \
  --arg title "$TITLE" \
  --arg price "$PRICE" \
  --arg rating "$RATING" \
  --arg review_count "$REVIEW_COUNT" \
  --argjson bullets "$BULLETS" \
  --argjson images "$IMAGES" \
  --argjson aplus_images "$APLUS_IMAGES" \
  --arg description "$DESCRIPTION" \
  '{
    asin: $asin,
    domain: $domain,
    url: $url,
    title: $title,
    price: $price,
    rating: $rating,
    review_count: $review_count,
    bullets: $bullets,
    images: $images,
    aplus_images: $aplus_images,
    description: $description
  }'
