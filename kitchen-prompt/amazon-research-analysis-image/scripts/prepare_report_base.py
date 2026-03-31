#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")


def safe_link_or_copy(src: Path, dst: Path, mode: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if mode == "symlink":
        try:
            dst.symlink_to(src)
            return
        except OSError:
            pass
    shutil.copy2(src, dst)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare ASIN folder layout for generate_multi_asin_report.py"
    )
    parser.add_argument("--run-dir", required=True, help="Path to amazon-research run directory")
    parser.add_argument(
        "--base-dir",
        default="",
        help="Output report base dir (default: <run-dir>/reports)",
    )
    parser.add_argument(
        "--mode",
        choices=("symlink", "copy"),
        default="symlink",
        help="Use symlink for speed; fallback to copy if needed.",
    )
    return parser.parse_args()


def collect_asins(products_dir: Path, reviews_dir: Path, summary_path: Path) -> set[str]:
    asins: set[str] = set()

    if products_dir.exists():
        for f in sorted(products_dir.glob("*.json")):
            stem = f.stem.upper()
            if ASIN_RE.match(stem):
                asins.add(stem)

    if reviews_dir.exists():
        for f in sorted(reviews_dir.glob("*-reviews.json")):
            stem = f.name.split("-reviews.json")[0].upper()
            if ASIN_RE.match(stem):
                asins.add(stem)

    if summary_path.exists():
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            for item in payload.get("products", []):
                asin = str(item.get("asin", "")).upper().strip()
                if ASIN_RE.match(asin):
                    asins.add(asin)
        except Exception:
            pass

    return asins


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    products_dir = run_dir / "products"
    reviews_dir = run_dir / "reviews"
    summary_path = run_dir / "summary.json"

    if not run_dir.exists():
        raise SystemExit(f"run-dir not found: {run_dir}")

    base_dir = Path(args.base_dir).expanduser() if args.base_dir else run_dir / "reports"
    base_dir = base_dir.resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    asins = collect_asins(products_dir, reviews_dir, summary_path)

    product_count = 0
    review_count = 0

    for asin in sorted(asins):
        asin_dir = base_dir / asin
        asin_dir.mkdir(parents=True, exist_ok=True)

        src_product = products_dir / f"{asin}.json"
        if src_product.exists():
            safe_link_or_copy(src_product, asin_dir / f"{asin}-product.json", args.mode)
            product_count += 1

        src_review = reviews_dir / f"{asin}-reviews.json"
        if src_review.exists():
            safe_link_or_copy(src_review, asin_dir / f"{asin}-reviews.json", args.mode)
            review_count += 1

    manifest = {
        "run_dir": str(run_dir),
        "base_dir": str(base_dir),
        "asin_count": len(asins),
        "product_files_mapped": product_count,
        "review_files_mapped": review_count,
        "mode": args.mode,
    }
    (base_dir / "report-input-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(str(base_dir))


if __name__ == "__main__":
    main()
