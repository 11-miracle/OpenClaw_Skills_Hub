#!/usr/bin/env python3
"""
scrape-reviews-batch.py — 差评采集主控（Apify-only, scenario-driven）
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--asin", required=True)
    p.add_argument("--domain", default="amazon.com")
    p.add_argument("--platform", default="amazon")
    p.add_argument("--total-reviews", type=int, default=None)
    p.add_argument("--intent", default="standard", choices=["quick", "standard", "deep", "batch"])
    p.add_argument("--review-policy", default="balanced", choices=["fast", "balanced", "strict"])
    p.add_argument("--max", type=int, default=None)
    p.add_argument("--output", required=True)
    return p.parse_args()


def log(msg: str) -> None:
    print(f"[scrape-reviews-batch {datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def calc_target(total_reviews: int | None, intent: str, review_policy: str, max_cap: int | None = None) -> int:
    multiplier_map = {"quick": 0.3, "standard": 1.0, "deep": 2.0, "batch": 0.5}
    policy_factor = {"fast": 0.7, "balanced": 1.0, "strict": 1.35}

    multiplier = multiplier_map.get(intent, 1.0)
    factor = policy_factor.get(review_policy, 1.0)

    if total_reviews is None or total_reviews <= 0:
        base = 150
    elif total_reviews < 200:
        base = total_reviews
    elif total_reviews <= 2000:
        base = max(50, int(total_reviews * 0.20))
    elif total_reviews <= 10000:
        base = max(100, int(total_reviews * 0.10))
    else:
        base = max(150, min(500, int(total_reviews * 0.05)))

    target = int(math.ceil(base * multiplier * factor))
    target = max(20, min(1000, target))
    if max_cap is not None and max_cap > 0:
        target = min(target, max_cap)
    return target


def min_sample_threshold(review_policy: str) -> int:
    return {"fast": 10, "balanced": 20, "strict": 30}.get(review_policy, 20)


def dedup(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in reviews:
        key = (str(r.get("title", ""))[:30] + str(r.get("body", ""))[:50]).strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def load_actor_chain(platform: str, scripts_dir: Path) -> list[str]:
    actor_map_path = scripts_dir / "actor-map.json"
    try:
        data = json.loads(actor_map_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}

    cfg = data.get(platform, {})
    reviews_cfg = cfg.get("reviews", {}) if isinstance(cfg, dict) else {}
    primary = str(reviews_cfg.get("primary_actor", "")).strip()
    fallback = reviews_cfg.get("fallback_actors", [])

    chain: list[str] = []
    if primary:
        chain.append(primary)
    if isinstance(fallback, list):
        for a in fallback:
            s = str(a).strip()
            if s and s not in chain:
                chain.append(s)
    return chain


def run_apify_actor(
    asin: str,
    domain: str,
    target: int,
    actor_id: str,
    platform: str,
    scripts_dir: Path,
) -> tuple[list[dict[str, Any]], int]:
    apify_sh = scripts_dir / "apify-reviews-batch.sh"
    if not apify_sh.exists():
        log("apify-reviews-batch.sh 不存在")
        return [], 1

    try:
        proc = subprocess.run(
            ["bash", str(apify_sh), asin, domain, str(target), actor_id, platform],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        log(f"actor 超时: {actor_id}")
        return [], 3
    except Exception as exc:
        log(f"actor 执行异常: {actor_id} err={exc}")
        return [], 1

    if proc.returncode != 0:
        log(f"actor 失败: {actor_id} exit={proc.returncode}")
        return [], proc.returncode

    try:
        raw = json.loads(proc.stdout or "[]")
    except Exception:
        raw = []

    normalized: list[dict[str, Any]] = []
    for r in raw:
        if not isinstance(r, dict):
            continue

        stars = r.get("ratingScore") or r.get("stars") or r.get("rating") or 0
        try:
            stars_val = float(str(stars).split()[0])
        except Exception:
            stars_val = 0.0

        if stars_val <= 0 or stars_val > 3:
            continue

        normalized.append(
            {
                "asin": asin,
                "stars": int(stars_val),
                "title": str(r.get("reviewTitle") or r.get("title") or ""),
                "body": str(r.get("reviewDescription") or r.get("body") or r.get("text") or ""),
                "date": str(r.get("reviewDate") or r.get("date") or ""),
                "verified": bool(r.get("isVerified") or r.get("verified") or False),
                "helpful": int(r.get("helpfulVotes") or r.get("helpful") or 0),
                "domain": domain,
                "source": f"apify:{actor_id}",
            }
        )

    log(f"actor 成功: {actor_id} -> {len(normalized)} 条")
    return normalized, 0


def evaluate_status(count: int, target: int, review_policy: str) -> tuple[str, int]:
    if count >= target:
        return "done", 0
    minimum = min_sample_threshold(review_policy)
    if count >= minimum:
        return "partial", 2
    return "insufficient", 3


def build_meta(
    *,
    asin: str,
    platform: str,
    count: int,
    target: int,
    source: str,
    actors_tried: list[str],
    note: str,
    review_policy: str,
) -> dict[str, Any]:
    status, _ = evaluate_status(count, target, review_policy)
    return {
        "asin": asin,
        "platform": platform,
        "total": count,
        "target": target,
        "status": status,
        "source": source,
        "actors_tried": actors_tried,
        "review_policy": review_policy,
        "min_sample": min_sample_threshold(review_policy),
        "note": note,
        "generated_at": datetime.now().isoformat(),
    }


def save_results(reviews: list[dict[str, Any]], meta: dict[str, Any], asin: str, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_file = output_dir / f"{asin}-reviews.json"
    meta_file = output_dir / f"{asin}-reviews-meta.json"
    raw_file.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return raw_file, meta_file


def read_total_reviews_from_product(output_dir: Path, asin: str) -> int | None:
    products_dir = output_dir.parent / "products"
    product_file = products_dir / f"{asin}.json"
    if not product_file.exists():
        return None

    try:
        payload = json.loads(product_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    raw = str(payload.get("review_count") or "0")
    try:
        return int("".join(ch for ch in raw if ch.isdigit()) or 0)
    except Exception:
        return None


def main() -> None:
    args = parse_args()

    scripts_dir = Path(__file__).resolve().parent
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    total_reviews = args.total_reviews
    if total_reviews is None:
        total_reviews = read_total_reviews_from_product(output_dir, args.asin)

    target = calc_target(total_reviews, args.intent, args.review_policy, args.max)
    minimum = min_sample_threshold(args.review_policy)
    log(
        f"目标数量: {target} [总评论={total_reviews}, 意图={args.intent}, 平台={args.platform}, 策略={args.review_policy}, 最低样本={minimum}]"
    )

    actor_chain = load_actor_chain(args.platform, scripts_dir)
    if not actor_chain:
        note = f"platform={args.platform} 未配置 reviews actor"
        meta = build_meta(
            asin=args.asin,
            platform=args.platform,
            count=0,
            target=target,
            source="none",
            actors_tried=[],
            note=note,
            review_policy=args.review_policy,
        )
        raw_file, meta_file = save_results([], meta, args.asin, output_dir)
        print(
            json.dumps(
                {
                    "status": "failed",
                    "total": 0,
                    "target": target,
                    "source": "none",
                    "note": note,
                    "raw_file": str(raw_file),
                    "meta_file": str(meta_file),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    best_reviews: list[dict[str, Any]] = []
    best_source = "none"
    actors_tried: list[str] = []

    for actor in actor_chain:
        reviews, code = run_apify_actor(args.asin, args.domain, target, actor, args.platform, scripts_dir)
        actors_tried.append(f"{actor}:exit={code}:count={len(reviews)}")

        if len(reviews) > len(best_reviews):
            best_reviews = reviews
            best_source = f"apify:{actor}"

        if code == 0 and len(reviews) >= target:
            break

    deduped = dedup(best_reviews)
    status, exit_code = evaluate_status(len(deduped), target, args.review_policy)

    if len(deduped) == 0:
        note = "未采集到有效差评，可能是平台评论不足、actor 限制或页面变更。"
    elif len(deduped) < minimum:
        note = f"仅采集到 {len(deduped)} 条，低于策略最低样本量 {minimum}。"
    elif len(deduped) < target:
        note = f"已采集 {len(deduped)} 条，低于目标 {target} 条。"
    else:
        note = ""

    meta = build_meta(
        asin=args.asin,
        platform=args.platform,
        count=len(deduped),
        target=target,
        source=best_source,
        actors_tried=actors_tried,
        note=note,
        review_policy=args.review_policy,
    )
    raw_file, meta_file = save_results(deduped, meta, args.asin, output_dir)

    print(
        json.dumps(
            {
                "status": status,
                "total": len(deduped),
                "target": target,
                "source": best_source,
                "note": note,
                "raw_file": str(raw_file),
                "meta_file": str(meta_file),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
