#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ISSUE_PATTERNS = {
    "功效不明显": [r"didn'?t work", r"no improvement", r"no difference", r"没效果", r"无明显改善"],
    "不耐受反应": [r"diarrhea", r"vomit", r"upset stomach", r"腹泻", r"呕吐", r"不适"],
    "适口性差": [r"won'?t eat", r"wouldn'?t eat", r"refused", r"smell", r"拒食", r"气味"],
    "包装品质问题": [r"broken seal", r"open", r"damaged", r"powder", r"封口", r"破损", r"受潮"],
    "价格性价比压力": [r"expensive", r"overpriced", r"waste of money", r"贵", r"性价比"],
    "售后信任问题": [r"refund", r"return", r"退货", r"退款", r"售后"],
}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value).strip()
        if text:
            return text
    return ""


def collect_review_texts(reviews_dir: Path) -> list[str]:
    texts: list[str] = []
    if not reviews_dir.exists():
        return texts

    for f in sorted(reviews_dir.glob("*-reviews.json")):
        payload = read_json(f)
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            text = first_non_empty(
                item.get("body"),
                item.get("text"),
                item.get("content"),
                item.get("review"),
                item.get("reviewText"),
            )
            if text:
                texts.append(text)
    return texts


def extract_top_issues(texts: list[str], top_k: int = 3) -> list[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        low = text.lower()
        for issue, patterns in ISSUE_PATTERNS.items():
            if any(re.search(pattern, low) for pattern in patterns):
                counter[issue] += 1
    if not counter:
        return ["功效不稳定", "体验一致性不足", "包装与服用便利性待优化"][:top_k]
    return [k for k, _ in counter.most_common(top_k)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Chinese image prompt draft from amazon run outputs.")
    parser.add_argument("--run-dir", required=True, help="Path to amazon-research run directory")
    parser.add_argument(
        "--output",
        default="",
        help="Output markdown path (default: <run-dir>/output/image-prompt-cn.md)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    summary_path = run_dir / "summary.json"
    reviews_dir = run_dir / "reviews"

    if not run_dir.exists():
        raise SystemExit(f"run-dir not found: {run_dir}")

    summary = read_json(summary_path) or {}
    query = first_non_empty(summary.get("query"), "该类目")
    products = summary.get("products", []) if isinstance(summary.get("products", []), list) else []
    first_product = products[0] if products else {}
    product_name = first_non_empty(
        first_product.get("title"),
        query,
    )

    texts = collect_review_texts(reviews_dir)
    issues = extract_top_issues(texts, top_k=3)
    issue_text = "、".join(issues)

    product_description_cn = (
        f"基于 {query} 类目低星评论证据，提出一款强调稳定体验与可持续服用的新产品方案。"
        f"重点针对 {issue_text} 三类高频痛点，通过结构与材质优化提升首用成功率、持续使用体验和信任感。"
    )

    image_prompt_structured_cn = f"""主体：{product_name}，单品主视图，突出改良版产品形态
关键部件清单：主容器、功能核心部件、密封结构、开合与取用结构、底座/支撑结构
连接与装配关系：关键部件连接清晰可装配，开合路径自然，不出现悬空或断裂连接
外形比例：主体比例均衡，便于单手操作，强调真实可量产外观
材质与工艺：以真实量产材质为主，表面处理克制，避免不现实材质组合
场景：干净中性台面或居家真实使用场景，突出“改进痛点后的使用体验”
灯光：柔和主光+轻辅光，阴影方向一致，保留适度细节层次
镜头与构图：3/4 视角，主体占比 70% 左右，背景简洁留白
风格：简约现代真实商品摄影感，避免海报化夸张表达
细节约束：围绕高频痛点 {issue_text} 可视化改良点，关键部件完整、连接合理、结构不冲突"""

    negative_prompt_cn = """禁止不可能结构、悬空部件、无连接漂浮、穿模、错位连接、关键部件缺失、重复部件、明显失衡比例、与功能冲突场景、卡通化渲染、过度装饰背景、文本水印污染、低清晰度、营销海报感强于真实商品主体"""

    output_path = Path(args.output).expanduser() if args.output else run_dir / "output" / "image-prompt-cn.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = (
        "# product_description_cn\n\n"
        f"{product_description_cn}\n\n"
        "# image_prompt_structured_cn\n\n"
        f"{image_prompt_structured_cn}\n\n"
        "# negative_prompt_cn\n\n"
        f"{negative_prompt_cn}\n"
    )
    output_path.write_text(content, encoding="utf-8")
    print(str(output_path))


if __name__ == "__main__":
    main()
