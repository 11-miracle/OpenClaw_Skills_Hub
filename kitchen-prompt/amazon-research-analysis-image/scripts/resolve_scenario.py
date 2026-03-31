#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")


def detect_scope(request: str) -> str:
    text = request.lower()
    has_bs = any(k in text for k in ["销量", "bestseller", "best sellers", "bestsellers"])
    has_nr = any(k in text for k in ["新品", "new release", "new releases", "new arrivals"])

    if has_bs and has_nr:
        return "both"
    if has_bs:
        return "bestsellers"
    if has_nr:
        return "new_releases"
    return "both"


def detect_top_n(request: str, default_n: int) -> int:
    patterns = [
        re.compile(r"前\s*(\d{1,3})"),
        re.compile(r"top\s*(\d{1,3})", re.IGNORECASE),
    ]
    for pat in patterns:
        m = pat.search(request)
        if m:
            try:
                v = int(m.group(1))
                if 1 <= v <= 100:
                    return v
            except Exception:
                pass
    return default_n


def detect_outputs(request: str, default_outputs: str) -> str:
    text = request.lower()
    if any(k in text for k in ["只要报告", "仅报告", "only report"]):
        return "report"
    if any(k in text for k in ["只要提示词", "仅提示词", "only prompt"]):
        return "prompt"
    return default_outputs


def detect_review_policy(request: str, default_policy: str) -> str:
    text = request.lower()
    if any(k in text for k in ["快速", "fast", "quick"]):
        return "fast"
    if any(k in text for k in ["严格", "严格采集", "strict", "深度"]):
        return "strict"
    return default_policy


def load_default_domain(platform: str, scripts_dir: Path) -> str:
    actor_map = scripts_dir / "actor-map.json"
    try:
        data = json.loads(actor_map.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return str(data.get(platform, {}).get("default_domain", "amazon.com"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resolve natural-language request into scenario.json")
    p.add_argument("--input", required=True, help="Keyword or ASIN")
    p.add_argument("--request", default="", help="Original user request for heuristic parsing")
    p.add_argument("--platform", default="amazon")
    p.add_argument("--domain", default="")
    p.add_argument("--intent", default="standard", choices=["quick", "standard", "deep", "batch"])
    p.add_argument("--scope", default="auto", choices=["auto", "bestsellers", "new_releases", "both"])
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--outputs", default="both", choices=["both", "report", "prompt"])
    p.add_argument("--review-policy", default="balanced", choices=["fast", "balanced", "strict"])
    p.add_argument("--out", default="", help="Write scenario json to this path")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    scripts_dir = Path(__file__).resolve().parent

    request_text = args.request.strip()
    domain = args.domain.strip() or load_default_domain(args.platform, scripts_dir)

    scope = args.scope
    if scope == "auto":
        scope = detect_scope(request_text)

    top_n = max(1, min(100, int(args.top_n)))
    top_n = detect_top_n(request_text, top_n)

    outputs = detect_outputs(request_text, args.outputs)
    review_policy = detect_review_policy(request_text, args.review_policy)

    seed_mode = "asin" if ASIN_RE.match(args.input.strip().upper()) else "keyword"

    scenario = {
        "platform": args.platform,
        "seed_mode": seed_mode,
        "input": args.input,
        "domain": domain,
        "intent": args.intent,
        "scope": scope,
        "top_n": top_n,
        "outputs": outputs,
        "review_policy": review_policy,
    }

    if args.out:
        out = Path(args.out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
        print(str(out))
    else:
        print(json.dumps(scenario, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
