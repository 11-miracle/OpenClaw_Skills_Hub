#!/usr/bin/env python3
"""
browser-reviews.py — 浏览器自动化爬取亚马逊差评（Level 2）
由 SKILL.md 流程中的 AI 调用 browser 工具执行，本脚本负责数据整合和站点切换逻辑

用法: python3 browser-reviews.py <ASIN> [domain] [min_reviews] [max_reviews]
退出码:
  0 = 成功，达到 min_reviews
  2 = 成功但不足 min_reviews（所有站点均尝试后）
  1 = 失败
"""

import sys
import json
import os
import re

ASIN        = sys.argv[1] if len(sys.argv) > 1 else ""
DOMAIN      = sys.argv[2] if len(sys.argv) > 2 else "amazon.com"
MIN_REVIEWS = int(sys.argv[3]) if len(sys.argv) > 3 else 100
MAX_REVIEWS = int(sys.argv[4]) if len(sys.argv) > 4 else 1000
REPORT_DIR  = f"/Users/macmini/.openclaw/workspace/reports/{ASIN}"
OUT_FILE    = f"{REPORT_DIR}/{ASIN}-reviews-raw.json"

# 站点切换优先级
DOMAIN_FALLBACK = [
    "amazon.com",
    "amazon.co.uk",
    "amazon.de",
    "amazon.co.jp",
]

# 站点 → 语言标注
DOMAIN_LANG = {
    "amazon.com":    "en",
    "amazon.co.uk":  "en",
    "amazon.de":     "de",
    "amazon.co.jp":  "ja",
}

os.makedirs(REPORT_DIR, exist_ok=True)

def review_url(domain, asin, page=1):
    return (f"https://www.{domain}/product-reviews/{asin}"
            f"?filterByStar=critical&sortBy=recent&pageNumber={page}")

def extract_reviews_js():
    """返回在浏览器页面中执行的 JS，提取当前页所有评论"""
    return """() => {
        const reviews = [];
        document.querySelectorAll('[data-hook="review"]').forEach(el => {
            const ratingEl = el.querySelector('[data-hook="review-star-rating"] .a-icon-alt')
                          || el.querySelector('[data-hook="cmps-review-star-rating"] .a-icon-alt');
            const titleEl  = el.querySelector('[data-hook="review-title"] span:not(.a-icon-alt)');
            const bodyEl   = el.querySelector('[data-hook="review-body"] span');
            const dateEl   = el.querySelector('[data-hook="review-date"]');
            const ratingRaw = ratingEl?.textContent?.trim() || '';
            const ratingNum = parseFloat(ratingRaw.split(' ')[0]) || 0;
            if (ratingNum <= 3 && ratingNum > 0) {
                reviews.push({
                    rating:   ratingNum,
                    title:    titleEl?.textContent?.trim()  || '',
                    body:     bodyEl?.textContent?.trim()   || '',
                    date:     dateEl?.textContent?.trim()   || '',
                    verified: !!el.querySelector('[data-hook="avp-badge"]')
                });
            }
        });
        const nextBtn = document.querySelector('li.a-last:not(.a-disabled) a');
        return JSON.stringify({ reviews, hasNext: !!nextBtn, url: location.href });
    }"""

def check_login_js():
    """检测是否已登录"""
    return """() => {
        const txt = document.querySelector('#nav-link-accountList-nav-line-1')?.textContent?.trim() || '';
        return JSON.stringify({ loggedIn: !txt.toLowerCase().includes('sign in'), displayText: txt });
    }"""

# 生成操作指令 JSON（供 AI 在 SKILL.md 流程中读取执行）
instructions = {
    "asin": ASIN,
    "domain": DOMAIN,
    "min_reviews": MIN_REVIEWS,
    "max_reviews": MAX_REVIEWS,
    "out_file": OUT_FILE,
    "domain_fallback_order": DOMAIN_FALLBACK,
    "domain_lang": DOMAIN_LANG,
    "steps": {
        "1_login_check": {
            "desc": "打开亚马逊首页，执行 check_login_js 检测登录状态",
            "url": f"https://www.{DOMAIN}",
            "js": check_login_js(),
            "on_not_logged_in": "聊天框提示：🔐 未检测到亚马逊登录状态，登录后回复「继续」效果更好，或回复「跳过」",
            "on_logged_in": "静默继续"
        },
        "2_paginate": {
            "desc": "翻页爬取差评，直到达到 max_reviews 或无 next page",
            "start_url": review_url(DOMAIN, ASIN, 1),
            "extract_js": extract_reviews_js(),
            "loop": "有 hasNext 且 已采集 < max_reviews → 翻下一页继续",
            "stop_conditions": ["hasNext == false", "已采集 >= max_reviews"],
            "max_pages": 100
        },
        "3_check_threshold": {
            "desc": "检查是否达到 min_reviews",
            "on_sufficient": "保存到 out_file，退出码 0",
            "on_insufficient": "触发站点切换流程"
        },
        "4_domain_switch": {
            "desc": "依次切换站点重试，直到达标或全部尝试",
            "order": [d for d in DOMAIN_FALLBACK if d != DOMAIN],
            "merge": "合并所有站点结果去重（按 title+body 前50字）",
            "on_all_failed": {
                "action": "保存现有数据，在报告中输出说明段落",
                "template": "⚠️ ASIN {asin} 在所有已尝试站点（{tried_domains}）差评总量不足{min}条，实际获取 {actual} 条，分析结果仅供参考。可能原因：商品评论数量较少 / 近期刚上架 / 该站点无此商品。",
                "exit_code": 2
            }
        }
    },
    "output_schema": {
        "reviews": [{"rating": "float", "title": "str", "body": "str", "date": "str", "verified": "bool", "domain": "str", "lang": "str"}],
        "meta": {
            "total": "int",
            "domains_tried": ["str"],
            "domains_success": {"amazon.com": "int"},
            "reached_minimum": "bool",
            "note": "str（不足时的说明）"
        }
    }
}

print(json.dumps(instructions, ensure_ascii=False, indent=2))
