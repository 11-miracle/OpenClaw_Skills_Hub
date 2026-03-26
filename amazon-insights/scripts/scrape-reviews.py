#!/usr/bin/env python3
"""
scrape-reviews.py — 亚马逊差评采集主控脚本（含完整降级链 + 硬出口）

用法:
  python3 scrape-reviews.py --asin <ASIN> [--domain <domain>] [--target <count>] [--output <dir>]

降级链：
  Level 1: Apify（90s 超时）
  Level 2: 浏览器自动化翻页（AI 通过 browser 工具执行）
  Level 3: 站点切换（仅 Level 2 < 20 条时触发）

硬出口规则（任意一条触发即停止，不再降级）：
  - 已采集 >= 目标数量
  - 连续3页无新数据
  - hasNext=false 且 已采集 >= 20 条（sufficient）
  - 所有站点完成（无论数量）
  - 全局超时 300s

退出码:
  0 = 成功（>= 目标数量）
  2 = 部分成功（20 <= 采集 < 目标）
  3 = 数据不足（< 20 条，但已尽力）
  1 = 系统错误

输出: <output>/<ASIN>-reviews-raw.json + <output>/<ASIN>-reviews-meta.json
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime

# 跨平台路径解析
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import get_paths, ensure_dirs

# ─── 参数解析 ───────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--asin",          required=True)
    p.add_argument("--domain",        default="amazon.com")
    p.add_argument("--target",        type=int,   default=None,
                   help="明确指定目标数量；不传则由 --total-reviews + --intent 自动计算")
    p.add_argument("--total-reviews", type=int,   default=None,
                   help="商品总评论数（从 product.json 读取），用于动态计算目标量")
    p.add_argument("--intent",        default="standard",
                   choices=["quick", "standard", "deep", "batch"],
                   help="用户意图：quick=快速扫描 / standard=默认 / deep=深度 / batch=批量对比")
    p.add_argument("--output",        default=None)
    return p.parse_args()

# ─── 动态目标数计算 ──────────────────────────────────────────────────────────

def calc_target(total_reviews: int | None, intent: str) -> int:
    """
    根据商品总评论数 + 用户意图，动态计算差评采集目标量。

    比例策略（基于总评论数）：
      总评论 < 200       → 采全部低星（无比例限制，上限 200）
      总评论 200–2000    → 采 20%，最少 50 条
      总评论 2000–10000  → 采 10%，最少 100 条
      总评论 > 10000     → 采  5%，最少 150 条，上限 500 条

    意图修正倍率：
      quick    → × 0.3（30–60 条，够做快速摘要）
      standard → × 1.0（默认）
      deep     → × 2.0（翻倍，深度分析）
      batch    → × 0.5（批量模式，单个 ASIN 减半）

    返回值永远在 [20, 1000] 之间。
    """
    INTENT_MULTIPLIER = {"quick": 0.3, "standard": 1.0, "deep": 2.0, "batch": 0.5}
    multiplier = INTENT_MULTIPLIER.get(intent, 1.0)

    if total_reviews is None or total_reviews <= 0:
        # 没有总评论数信息，用保守默认值
        base = 150
    elif total_reviews < 200:
        base = total_reviews          # 全采
    elif total_reviews <= 2000:
        base = max(50,  int(total_reviews * 0.20))
    elif total_reviews <= 10000:
        base = max(100, int(total_reviews * 0.10))
    else:
        base = max(150, min(500, int(total_reviews * 0.05)))

    target = int(math.ceil(base * multiplier))
    # 硬边界：最少 20 条（分析基础），最多 1000 条
    return max(20, min(1000, target))

# ─── 工具函数 ───────────────────────────────────────────────────────────────

_P = get_paths()
SCRIPTS_DIR = _P["scripts"]

DOMAIN_FALLBACK = ["amazon.com", "amazon.co.uk", "amazon.de", "amazon.co.jp"]
DOMAIN_LANG     = {"amazon.com": "en", "amazon.co.uk": "en", "amazon.de": "de", "amazon.co.jp": "ja"}

def log(msg):
    print(f"[scrape-reviews {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)

def dedup(reviews):
    """按 title+body 前50字去重"""
    seen = set()
    result = []
    for r in reviews:
        key = (str(r.get("title",""))[:30] + str(r.get("body",""))[:50]).strip()
        if key and key not in seen:
            seen.add(key)
            result.append(r)
    return result

def save_results(reviews, meta, asin, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    raw_path  = os.path.join(output_dir, f"{asin}-reviews-raw.json")
    meta_path = os.path.join(output_dir, f"{asin}-reviews-meta.json")
    with open(raw_path,  "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta,    f, ensure_ascii=False, indent=2)
    log(f"已保存: {len(reviews)} 条评论 → {raw_path}")
    return raw_path, meta_path

# ─── Level 1：Apify ─────────────────────────────────────────────────────────

def run_apify(asin, domain, target):
    log("Level 1: 启动 Apify...")
    apify_sh = os.path.join(SCRIPTS_DIR, "apify-reviews.sh")
    if not os.path.exists(apify_sh):
        log("apify-reviews.sh 不存在，跳过 Level 1")
        return [], 1

    try:
        result = subprocess.run(
            ["bash", apify_sh, asin, domain, str(target)],
            capture_output=True, text=True, timeout=100
        )
        if result.returncode == 3:
            log("Level 1: 90s 超时")
            return [], 3
        if result.returncode == 2:
            log("Level 1: 返回0条")
            return [], 2
        if result.returncode != 0:
            log(f"Level 1: 失败 exit={result.returncode}")
            return [], result.returncode

        reviews = json.loads(result.stdout or "[]")
        # 标准化字段
        normalized = []
        for r in reviews:
            normalized.append({
                "rating":   float(r.get("ratingScore") or r.get("rating") or 0),
                "title":    str(r.get("reviewTitle")  or r.get("title")  or ""),
                "body":     str(r.get("reviewDescription") or r.get("body") or r.get("text") or ""),
                "date":     str(r.get("reviewDate")   or r.get("date")   or ""),
                "verified": bool(r.get("isVerified")  or r.get("verified") or False),
                "domain":   domain,
                "lang":     DOMAIN_LANG.get(domain, "en"),
                "source":   "apify"
            })
        log(f"Level 1: 获取 {len(normalized)} 条")
        return normalized, 0
    except subprocess.TimeoutExpired:
        log("Level 1: 进程超时")
        return [], 3
    except Exception as e:
        log(f"Level 1: 异常 {e}")
        return [], 1

# ─── Level 2 / Level 3：浏览器翻页指令生成 ──────────────────────────────────
# AI 主流程通过读取 scrape-reviews.py 的输出 JSON 来执行浏览器操作
# 本脚本输出操作指令，AI 按指令执行后将结果写回 output/<ASIN>-reviews-raw.json

def build_browser_instructions(asin, domain, target, output_dir, domains_to_try):
    """生成供 AI 执行的浏览器操作指令"""

    extract_js = """() => {
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
        return JSON.stringify({ reviews, hasNext: !!nextBtn });
    }"""

    instructions = {
        "mode": "browser_level2",
        "asin": asin,
        "target": target,
        "output_file": os.path.join(output_dir, f"{asin}-reviews-raw.json"),
        "meta_file":   os.path.join(output_dir, f"{asin}-reviews-meta.json"),
        "domains_to_try": domains_to_try,
        "extract_js": extract_js,
        "hard_stop_rules": {
            "collected_gte_target":      "采集数 >= 目标数，立即停止",
            "consecutive_empty_pages_3": "连续3页无新数据，停止当前站点",
            "max_pages_per_domain":      15,
            "global_timeout_seconds":    300,
            "insufficient_threshold":    20,
            "note": "hasNext=false 且已采集 >= 20 条 → 当前站点停止，不进下一站点"
        },
        "url_template": "https://www.{domain}/product-reviews/{asin}?filterByStar=critical&sortBy=recent&pageNumber={page}",
        "merge_rule": "按 title+body 前50字去重，合并所有站点结果",
        "output_schema": {
            "reviews": [{"rating": "float", "title": "str", "body": "str",
                         "date": "str", "verified": "bool", "domain": "str",
                         "lang": "str", "source": "str"}],
            "meta": {
                "asin": "str",
                "total": "int",
                "domains_tried": ["str"],
                "domains_success": {"amazon.com": "int"},
                "reached_minimum": "bool",
                "status": "done|partial|insufficient|failed",
                "note": "str",
                "source": "browser-level2|browser-level3"
            }
        }
    }
    return instructions

# ─── 状态评估 ────────────────────────────────────────────────────────────────

def evaluate_status(count, target):
    """根据数量返回 status 和退出码"""
    if count >= target:
        return "done", 0
    elif count >= 20:
        return "partial", 2
    else:
        return "insufficient", 3

def build_meta(asin, reviews, domains_tried, domains_success, target, source, note=""):
    count = len(reviews)
    status, _ = evaluate_status(count, target)
    reached = count >= target

    # 不足时的标准化提示（规则引擎生成，不依赖 LLM）
    if not reached and not note:
        tried_str = "、".join(domains_tried)
        if count == 0:
            note = (f"⚠️ ASIN {asin} 在所有已尝试站点（{tried_str}）未采集到差评。"
                    f"可能原因：商品较新 / 差评极少 / Amazon 页面结构变更。分析结果仅供参考。")
        elif count < 20:
            note = (f"⚠️ ASIN {asin} 差评数量较少（共 {count} 条），"
                    f"已尝试：{tried_str}。分析结论置信度有限，建议参考同类竞品数据。")
        else:
            note = (f"⚠️ ASIN {asin} 实际采集 {count} 条差评（目标 {target} 条），"
                    f"Amazon 翻页限制导致未能获取更多。以下分析基于现有数据。")

    return {
        "asin":            asin,
        "total":           count,
        "target":          target,
        "domains_tried":   domains_tried,
        "domains_success": domains_success,
        "reached_minimum": reached,
        "status":          status,
        "note":            note if not reached else "",
        "source":          source,
        "generated_at":    datetime.now().isoformat()
    }

# ─── 主流程 ──────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    asin   = args.asin
    domain = args.domain
    intent = args.intent
    P = ensure_dirs(asin)
    output_dir = args.output or P["report_dir"]

    os.makedirs(output_dir, exist_ok=True)

    # ── 动态计算目标数量 ─────────────────────────────────────────────────────
    if args.target is not None:
        # 用户/调用方明确指定，直接使用
        target = args.target
        log(f"目标数量（指定）: {target}")
    else:
        # 优先读 product.json 获取总评论数
        total_reviews = args.total_reviews
        if total_reviews is None:
            product_file = os.path.join(P["report_dir"], f"{asin}-product.json")
            if os.path.exists(product_file):
                try:
                    p = json.load(open(product_file, "r", encoding="utf-8"))
                    raw = str(p.get("review_count") or "0")
                    # 处理 "52,541 ratings" 这类格式
                    total_reviews = int("".join(filter(str.isdigit, raw)) or 0)
                    log(f"从 product.json 读取总评论数: {total_reviews}")
                except Exception as e:
                    log(f"读取 product.json 失败: {e}，使用默认值")
                    total_reviews = None

        target = calc_target(total_reviews, intent)
        log(f"目标数量（动态计算）: {target}  "
            f"[总评论={total_reviews}, 意图={intent}, 结果={target}]")

    log(f"开始采集 ASIN={asin} domain={domain} target={target} intent={intent}")

    all_reviews = []
    domains_tried   = []
    domains_success = {}
    source = "unknown"

    # ── Level 1: Apify ──────────────────────────────────────────────────────
    apify_reviews, apify_code = run_apify(asin, domain, target)

    if apify_code == 0 and len(apify_reviews) >= 20:
        all_reviews     = apify_reviews
        domains_tried   = [domain]
        domains_success = {domain: len(apify_reviews)}
        source          = "apify"
        log(f"Level 1 成功: {len(all_reviews)} 条，流程结束")

    else:
        # ── Level 2: 浏览器翻页（输出指令供 AI 执行）──────────────────────
        log(f"Level 1 不足（{len(apify_reviews)} 条），切换 Level 2: 浏览器自动化")

        # 确定 Level 3 需要尝试的站点
        # Level 2 < 20 条时才触发 Level 3，否则只跑主站点
        domains_for_browser = [domain]
        # Level 3 备用站点列表（在指令中提供，AI 按需使用）
        fallback_domains = [d for d in DOMAIN_FALLBACK if d != domain]

        instructions = build_browser_instructions(
            asin, domain, target, output_dir,
            domains_to_try=domains_for_browser
        )
        instructions["fallback_domains"] = fallback_domains
        instructions["level3_trigger"]   = "当前站点采集 < 20 条时，才依次尝试 fallback_domains"

        # 输出指令 JSON（AI 读取后执行浏览器操作）
        print(json.dumps({
            "status":       "need_browser",
            "instructions": instructions
        }, ensure_ascii=False, indent=2))

        # 等待 AI 写入结果文件（最多 300s）
        raw_path  = os.path.join(output_dir, f"{asin}-reviews-raw.json")
        meta_path = os.path.join(output_dir, f"{asin}-reviews-meta.json")
        waited = 0
        while waited < 300:
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("status") in ("done", "partial", "insufficient", "failed"):
                    log(f"Level 2/3 完成: status={meta['status']}, total={meta.get('total',0)}")
                    # 读取评论数据并直接返回（meta 已由 AI 写入）
                    sys.exit(0 if meta["status"] == "done" else
                             2 if meta["status"] == "partial" else 3)
            time.sleep(5)
            waited += 5

        # 超时降级：用 Apify 已有数据 + 空白 meta 兜底
        log("Level 2 等待超时（300s），使用现有数据兜底")
        all_reviews     = apify_reviews  # 可能为空
        domains_tried   = [domain]
        domains_success = {domain: len(apify_reviews)}
        source          = "apify-partial"

    # ── 保存结果（Apify 路径） ───────────────────────────────────────────────
    status, exit_code = evaluate_status(len(all_reviews), target)
    meta = build_meta(asin, all_reviews, domains_tried, domains_success, target, source)
    save_results(all_reviews, meta, asin, output_dir)

    # 标准输出最终状态摘要
    print(json.dumps({
        "status":   status,
        "total":    len(all_reviews),
        "target":   target,
        "source":   source,
        "note":     meta["note"],
        "raw_file": os.path.join(output_dir, f"{asin}-reviews-raw.json"),
        "meta_file": os.path.join(output_dir, f"{asin}-reviews-meta.json")
    }, ensure_ascii=False, indent=2))

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
