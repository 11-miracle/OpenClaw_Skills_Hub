# 站点域名映射表

用户输入关键词 → 对应域名：

| 用户说法 | 域名 |
|---|---|
| 不指定（默认） | amazon.com |
| 美国、美站、us | amazon.com |
| 日本、日站、jp | amazon.co.jp |
| 英国、英站、uk | amazon.co.uk |
| 德国、德站、de | amazon.de |
| 法国、法站、fr | amazon.fr |
| 加拿大、加站、ca | amazon.ca |
| 意大利、意站、it | amazon.it |
| 西班牙、西站、es | amazon.es |
| 墨西哥、墨站、mx | amazon.com.mx |
| 印度、印站、in | amazon.in |
| 澳大利亚、澳站、au | amazon.com.au |

# Apify Actor 说明

## 评论爬取（Level 1）
- Actor: `delicious_zebu/amazon-reviews-scraper-with-advanced-filters`
- Actor ID: `8vhDnIX6dStLlGVr7`
- 评分: 4.47/5，成功率 99.9%
- 差评过滤: `["1 star only", "2 star only", "3 star only"]`
- 排序: `["Most recent"]`
- 去重: `unique_only: true`
- **注意**: 需要订阅（$49/月），免费试用期可用；若返回 `actor-is-not-rented` 自动降级 Level 2

## 商品信息（备用）
- Actor: `junglee/amazon-product-scraper`
- 当直接爬取失败时降级使用

# 评论爬取降级链

## Level 1 → Level 2 触发条件
- Apify 返回退出码 2（0条）
- Apify 返回退出码 3（90s超时）
- Apify 返回退出码 1（失败）
- 获取数量 < 20 条

## Level 2 → Level 3 触发条件
- 浏览器自动化检测到无 next page 按钮
- 浏览器自动化获取数量 < 20 条
- 用户回复「跳过」（未登录场景）

## Level 3 站点优先级（差评资源最丰富）
1. `amazon.co.uk` — 英语，翻译成本低
2. `amazon.de` — 德语，翻译后分析
3. `amazon.co.jp` — 日语，翻译后分析
4. 用现有数据继续（用户选择跳过）

# 账号轮换 Token 命名规范

环境变量命名：`APIFY_TOKEN_1`, `APIFY_TOKEN_2`, `APIFY_TOKEN_3` ...

OpenClaw 配置命令：
```bash
openclaw config set skills.entries.amazon-insights.env.APIFY_TOKEN_1 "token_A"
openclaw config set skills.entries.amazon-insights.env.APIFY_TOKEN_2 "token_B"
```

状态文件路径：`~/.openclaw/workspace/memory/apify-token-state.json`
```json
{
  "apify_token_index": 0
}
```
