#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


# Shared-skill defaults: operate on the caller's workspace rather than the skill folder.
DEFAULT_BASE_DIR = Path.cwd() / "reports"
DEFAULT_OUTPUT_DIR = Path.cwd() / "output"

REVIEW_FILE_PRIORITY = (
    "reviews-bad.json",
    "{asin}-reviews-raw.json",
    "reviews-raw.json",
    "{asin}-reviews.json",
    "reviews.json",
)

STAGE_ORDER = [
    "认知与下单",
    "收货与开箱",
    "首次使用",
    "持续服用",
    "问题处理与复购",
]

EMOTION_ORDER = [
    "失望",
    "担忧",
    "愤怒",
    "后悔",
    "反感",
    "不信任",
]

EMOTION_COLORS = {
    "失望": "#4f46e5",
    "担忧": "#f59e0b",
    "愤怒": "#dc2626",
    "后悔": "#8b5cf6",
    "反感": "#0f766e",
    "不信任": "#475569",
}

APPEALS_COLORS = {
    "Price": "#ef4444",
    "Availability": "#f59e0b",
    "Packaging": "#d97706",
    "Performance": "#2563eb",
    "Ease of Use": "#14b8a6",
    "Assurances": "#7c3aed",
    "Life Cycle Cost": "#64748b",
    "Social Acceptance": "#f43f5e",
}

KNOWN_BRANDS = (
    "Amazon Brand - Wag",
    "PetLab Co.",
    "Purina Pro Plan",
    "Nutramax",
    "Native Pet",
    "Pet Naturals",
    "Doggie Dailies",
    "VetOne",
    "VetIQ",
    "Royal Canin",
    "Honest Paws",
    "Fera Pets",
    "TummyWorks",
    "Dinovite",
    "VetriScience",
    "Vetnique",
    "NaturVet",
    "Nutri-Vet",
)

TERM_MAP = {
    "didn't work": "无明显改善",
    "didnt work": "无明显改善",
    "doesn't work": "无明显改善",
    "no difference": "无明显改善",
    "no improvement": "无明显改善",
    "waste of money": "浪费钱",
    "diarrhea": "腹泻",
    "diarrhoea": "腹泻",
    "vomit": "呕吐",
    "vomiting": "呕吐",
    "made him sick": "吃后不适",
    "made her sick": "吃后不适",
    "upset stomach": "胃部不适",
    "itch": "瘙痒",
    "itchy": "瘙痒",
    "paw licking": "舔爪",
    "licking paws": "舔爪",
    "would not eat": "拒食",
    "won't eat": "拒食",
    "wouldn't eat": "拒食",
    "smell is terrible": "气味差",
    "smells terrible": "气味差",
    "stinks": "气味差",
    "open": "封口异常",
    "broken seal": "封口异常",
    "hard as a brick": "质地变硬",
    "rock solid": "质地变硬",
    "powder": "粉末化",
    "crumbs": "碎屑多",
    "expensive": "价格高",
    "overpriced": "性价比低",
    "refund": "退款问题",
    "return": "退货问题",
    "new formula": "配方变更",
    "changed formula": "配方变更",
    "different than before": "版本不一致",
    "late": "发货延迟",
    "shipping": "配送问题",
    "out of stock": "缺货",
    "subscription": "长期成本",
    "too many": "用量高",
    "plastic": "包装材质顾虑",
    "artificial": "成分顾虑",
}

APPEALS_RULES = [
    {
        "id": "refund_support",
        "appeals_l1": "Assurances",
        "appeals_l2": "退款/售后承诺",
        "emotion_major": "不信任",
        "emotion_type": "售后受挫",
        "journey_stage": "问题处理与复购",
        "severity": 4.7,
        "patterns": ("refund", "non-refundable", "couldn't return", "could not return", "no returns", "return"),
        "reason": "用户在出现问题后没有获得与承诺匹配的退款或售后支持。",
        "keywords": ("退款", "退货", "售后"),
        "improvement": "明确退货政策、补充售后补偿机制，并在问题场景下提供快速客服响应。",
        "unmet_need": "用户需要可预期、可兑现的售后保障，而不是出问题后自行承担损失。",
    },
    {
        "id": "gi_reaction",
        "appeals_l1": "Performance",
        "appeals_l2": "服用后不耐受/副作用",
        "emotion_major": "担忧",
        "emotion_type": "安全顾虑",
        "journey_stage": "首次使用",
        "severity": 5.0,
        "patterns": (
            "diarrhea",
            "diarrhoea",
            "vomit",
            "vomiting",
            "threw up",
            "throw up",
            "made him sick",
            "made her sick",
            "made my dog sick",
            "upset stomach",
            "stomach pain",
            "blood",
        ),
        "reason": "用户反馈服用后出现腹泻、呕吐或胃部不适，担心产品本身带来负面反应。",
        "keywords": ("腹泻", "呕吐", "不耐受"),
        "improvement": "优化菌株与辅料耐受性，补充敏感犬过渡喂养方案，并降低首次服用刺激。",
        "unmet_need": "用户需要对敏感犬更温和、更低风险的肠胃支持方案。",
    },
    {
        "id": "packaging_quality",
        "appeals_l1": "Packaging",
        "appeals_l2": "包装破损/品质异常",
        "emotion_major": "愤怒",
        "emotion_type": "品质失控",
        "journey_stage": "收货与开箱",
        "severity": 4.5,
        "patterns": (
            "open",
            "opened",
            "broken seal",
            "damaged",
            "hard as a brick",
            "rock solid",
            "stuck together",
            "crumbly",
            "crumbs",
            "powdery",
            "melted",
            "expired",
            "arrived hot",
            "warm",
        ),
        "reason": "用户在收货阶段遇到封口、硬块、粉化或新鲜度异常，对品质与履约稳定性产生怀疑。",
        "keywords": ("封口异常", "硬块", "新鲜度"),
        "improvement": "加强封签与阻隔包装，优化仓配温控，并针对易硬化剂型追加质检节点。",
        "unmet_need": "用户需要开箱即可信的品质状态，而不是靠运气判断是否变质或受潮。",
    },
    {
        "id": "palatability",
        "appeals_l1": "Ease of Use",
        "appeals_l2": "适口性/服用通过率",
        "emotion_major": "反感",
        "emotion_type": "拒食抗拒",
        "journey_stage": "首次使用",
        "severity": 4.2,
        "patterns": (
            "would not eat",
            "wouldn't eat",
            "won't eat",
            "will not eat",
            "refused",
            "won't touch",
            "smell is terrible",
            "smells terrible",
            "smell bad",
            "stinks",
            "spits it out",
            "pick them out",
        ),
        "reason": "用户认为产品气味、口感或颗粒形态不佳，导致狗狗拒食，无法稳定服用。",
        "keywords": ("拒食", "气味差", "服用困难"),
        "improvement": "优化风味掩盖与质地控制，缩小颗粒或提供粉末/小袋等更容易喂食的剂型。",
        "unmet_need": "用户需要挑食犬也愿意持续服用的高通过率剂型。",
    },
    {
        "id": "no_effect",
        "appeals_l1": "Performance",
        "appeals_l2": "核心功效未达预期",
        "emotion_major": "失望",
        "emotion_type": "功效落空",
        "journey_stage": "持续服用",
        "severity": 4.3,
        "patterns": (
            "didn't work",
            "didnt work",
            "doesn't work",
            "doesnt work",
            "no difference",
            "made no difference",
            "did nothing",
            "nothing happened",
            "no improvement",
            "did not help",
            "didn't help",
            "doesn't help",
            "still itching",
            "still scratching",
            "still licking",
        ),
        "reason": "用户认为持续使用后仍未见明显改善，核心功效没有兑现。",
        "keywords": ("无明显改善", "功效落空", "持续症状"),
        "improvement": "收窄核心功效承诺，明确起效周期和适用边界，并校准产品定位与用户预期。",
        "unmet_need": "用户需要更稳定、可预期的核心功效，而不是过度承诺后的失望体验。",
    },
    {
        "id": "price_value",
        "appeals_l1": "Price",
        "appeals_l2": "价格/性价比失衡",
        "emotion_major": "后悔",
        "emotion_type": "价值落差",
        "journey_stage": "认知与下单",
        "severity": 3.8,
        "patterns": ("expensive", "overpriced", "pricey", "too expensive", "very expensive", "$34"),
        "reason": "用户感知价格偏高，但实际体验没有匹配到预期价值。",
        "keywords": ("价格高", "性价比低", "价值落差"),
        "improvement": "重新梳理价格带话术，补充功效边界与真实使用说明，避免高价但低感知价值。",
        "unmet_need": "用户需要价格与体验更匹配的价值感，而不是高价低感知收益。",
    },
    {
        "id": "formula_change",
        "appeals_l1": "Life Cycle Cost",
        "appeals_l2": "版本变更/长期稳定性",
        "emotion_major": "不信任",
        "emotion_type": "版本断层",
        "journey_stage": "问题处理与复购",
        "severity": 4.0,
        "patterns": (
            "new formula",
            "changed formula",
            "formula changed",
            "not the same",
            "different than before",
            "used to work",
            "packaging may vary",
        ),
        "reason": "用户认为版本、配方或包装变化影响了复购稳定性，对长期使用成本和体验一致性产生顾虑。",
        "keywords": ("配方变更", "版本不一致", "复购风险"),
        "improvement": "在版本更新时明确说明变化点，并确保新旧版本的核心体验不会突然断层。",
        "unmet_need": "用户需要复购时体验稳定可预测，而不是每次买到不同版本。",
    },
    {
        "id": "delivery_availability",
        "appeals_l1": "Availability",
        "appeals_l2": "配送/到货可获得性",
        "emotion_major": "愤怒",
        "emotion_type": "履约不顺",
        "journey_stage": "认知与下单",
        "severity": 3.7,
        "patterns": ("late", "shipping", "delivery", "out of stock", "delayed"),
        "reason": "用户在购买或配送阶段体验不顺，影响对产品整体可获得性的判断。",
        "keywords": ("配送问题", "到货延迟", "缺货"),
        "improvement": "提升库存与配送透明度，减少缺货和延迟，降低购买链路中的不确定性。",
        "unmet_need": "用户需要稳定可买、快速到货的履约体验。",
    },
    {
        "id": "dosage_cost",
        "appeals_l1": "Life Cycle Cost",
        "appeals_l2": "用量/长期成本偏高",
        "emotion_major": "后悔",
        "emotion_type": "持续成本焦虑",
        "journey_stage": "持续服用",
        "severity": 3.5,
        "patterns": ("too many", "twice a day", "runs out", "subscription", "lasted only", "not enough servings"),
        "reason": "用户觉得持续服用所需剂量、频次或订阅成本过高，长期使用性价比不足。",
        "keywords": ("用量高", "长期成本", "消耗快"),
        "improvement": "优化单次剂量与包装规格，并更清楚地说明不同犬体型下的真实使用周期。",
        "unmet_need": "用户需要更可持续的长期使用成本，而不是高频复购压力。",
    },
    {
        "id": "social_acceptance",
        "appeals_l1": "Social Acceptance",
        "appeals_l2": "成分/形象接受度",
        "emotion_major": "担忧",
        "emotion_type": "成分顾虑",
        "journey_stage": "认知与下单",
        "severity": 3.2,
        "patterns": ("artificial", "plastic", "chemical", "unsafe ingredients", "smells like chemicals"),
        "reason": "用户对成分、包装材质或整体形象产生顾虑，担心不符合自身标准。",
        "keywords": ("成分顾虑", "材质顾虑", "形象接受度"),
        "improvement": "提升成分与材质透明度，减少让用户产生负面联想的表达与包装感知。",
        "unmet_need": "用户需要更值得信赖、社会接受度更高的成分和包装表达。",
    },
]

DEFAULT_RULE = {
    "id": "generic_dissatisfaction",
    "appeals_l1": "Performance",
    "appeals_l2": "泛化负反馈",
    "emotion_major": "失望",
    "emotion_type": "体验不及预期",
    "journey_stage": "持续服用",
    "severity": 3.2,
    "reason": "评论表达了明确不满，但没有足够关键词指向更细的二级问题。",
    "keywords": ("体验不及预期",),
    "improvement": "补充更清晰的使用说明和适用边界，并持续收集原始评论以细化问题标签。",
    "unmet_need": "用户希望产品表现与预期更一致。",
}


def pain_strength_label(severity: float) -> str:
    return "strong" if severity >= 4.0 else "weak"


def usage_frequency_label(count: int, total: int) -> str:
    if total <= 0:
        return "low"
    return "high" if count >= max(2, total * 0.2) else "low"


def quadrant_name(strength: str, frequency: str) -> str:
    if strength == "strong" and frequency == "high":
        return "刚需高频"
    if strength == "strong" and frequency == "low":
        return "刚需低频"
    if strength == "weak" and frequency == "high":
        return "爽点驱动"
    return "痒点驱动"


def build_pain_pleasure_itch_summary(voice_pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not voice_pool:
        return []

    total = len(voice_pool)
    pain_rep = representative_row(voice_pool)
    avg_severity = sum(row["severity_score"] for row in voice_pool) / total
    pain_strength = pain_strength_label(avg_severity)
    pain_frequency = usage_frequency_label(total, total)
    summary_rows = [
        {
            "need_dimension": "Pain",
            "evidence_level": "direct",
            "pain_strength": pain_strength,
            "usage_frequency": pain_frequency,
            "matrix_quadrant": quadrant_name(pain_strength, pain_frequency),
            "count": total,
            "share": 1.0,
            "related_appeals": [name for name, _ in Counter(row["appeals_l1"] for row in voice_pool).most_common(3)],
            "related_journey_stage": [name for name, _ in Counter(row["journey_stage"] for row in voice_pool).most_common(3)],
            "user_state": pain_rep["emotion_reason"],
            "product_strategy": pain_rep["improvement_suggestion"],
            "opportunity_statement": pain_rep["unmet_need"],
            "representative_comment": pain_rep["original_text"],
            "representative_cn": pain_rep["chinese_interpretation"],
        }
    ]

    summary_rows.extend(
        [
            {
                "need_dimension": "Pleasure",
                "evidence_level": "insufficient",
                "pain_strength": "weak",
                "usage_frequency": "high",
                "matrix_quadrant": "爽点驱动",
                "count": 0,
                "share": 0.0,
                "related_appeals": [],
                "related_journey_stage": [],
                "user_state": "当前低星样本未提供即时满足或超预期体验的直接证据。",
                "product_strategy": "补充正向样本后再验证即时反馈、服用体验和超预期满足。",
                "opportunity_statement": "证据不足：当前低星样本只验证到痛点，尚未验证可成立的爽点机会。",
                "representative_comment": "",
                "representative_cn": "",
            },
            {
                "need_dimension": "Itch",
                "evidence_level": "insufficient",
                "pain_strength": "weak",
                "usage_frequency": "low",
                "matrix_quadrant": "痒点驱动",
                "count": 0,
                "share": 0.0,
                "related_appeals": [],
                "related_journey_stage": [],
                "user_state": "当前低星样本未提供身份认同、理想自我或生活方式投射的直接证据。",
                "product_strategy": "补充正向评价或品牌表达样本后再验证身份感与向往型机会。",
                "opportunity_statement": "证据不足：当前低星样本只验证到痛点，尚未验证可成立的痒点机会。",
                "representative_comment": "",
                "representative_cn": "",
            },
        ]
    )
    return summary_rows


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return ""


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value))).strip()


def parse_rating(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(value))
    return float(match.group(1)) if match else None


def parse_price(value: Any) -> float | None:
    if value in (None, ""):
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(value).replace(",", ""))
    return float(match.group(1)) if match else None


def parse_review_date(value: Any) -> dt.date | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        pass
    match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}", text)
    if match:
        return dt.datetime.strptime(match.group(0), "%B %d, %Y").date()
    return None


def normalize_review_text(review: dict[str, Any]) -> str:
    parts = []
    for key in (
        "title",
        "headline",
        "reviewTitle",
        "t",
        "body",
        "b",
        "text",
        "content",
        "review",
        "reviewDescription",
    ):
        value = review.get(key)
        if value:
            parts.append(str(value))
    return normalize_space(" ".join(parts))


def load_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        starts = [index for index in (text.find("["), text.find("{")) if index != -1]
        if not starts:
            raise
        snippet = text[min(starts):].lstrip()
        payload, _ = decoder.raw_decode(snippet)
        return payload


def flatten_review_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("reviews", "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def infer_brand(product_title: str, explicit_brand: str = "") -> str:
    clean_brand = normalize_space(explicit_brand) if explicit_brand else ""
    if clean_brand:
        return clean_brand
    title = normalize_space(product_title)
    for brand in KNOWN_BRANDS:
        if title.startswith(brand):
            return brand
    return title.split()[0] if title else "UNKNOWN"


def detect_terms(text: str) -> list[str]:
    lowered = text.lower()
    terms = []
    for pattern, label in TERM_MAP.items():
        if pattern in lowered and label not in terms:
            terms.append(label)
    return terms


def choose_primary_rule(text: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    lowered = text.lower()
    candidates = []
    matched_terms = detect_terms(text)

    for rule in APPEALS_RULES:
        matched_patterns = [pattern for pattern in rule["patterns"] if pattern in lowered]
        if not matched_patterns:
            continue
        score = (len(matched_patterns) * 10) + int(rule["severity"] * 2)
        candidates.append(
            {
                "rule": rule,
                "score": score,
                "patterns": matched_patterns,
            }
        )

    if not candidates:
        return DEFAULT_RULE, [], matched_terms

    candidates.sort(key=lambda item: (item["score"], item["rule"]["severity"]), reverse=True)
    return candidates[0]["rule"], candidates, matched_terms


def severity_label(value: float) -> str:
    if value >= 4.6:
        return "极高"
    if value >= 4.0:
        return "高"
    if value >= 3.3:
        return "中"
    return "低"


def truncate(text: str, limit: int = 120) -> str:
    clean = normalize_space(text)
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def compose_chinese_interpretation(rule: dict[str, Any], surface_terms: list[str]) -> str:
    if surface_terms:
        return f"{rule['reason']} 具体表现为：{'、'.join(surface_terms[:4])}。"
    return rule["reason"]


def annotate_review(review_row: dict[str, Any]) -> dict[str, Any]:
    text = review_row["original_text"]
    rating = float(review_row["rating"])
    primary_rule, candidates, surface_terms = choose_primary_rule(text)

    related_dimensions = []
    for candidate in candidates[:3]:
        dimension = candidate["rule"]["appeals_l1"]
        if dimension not in related_dimensions:
            related_dimensions.append(dimension)

    keywords = []
    for token in primary_rule["keywords"]:
        if token not in keywords:
            keywords.append(token)
    for token in surface_terms:
        if token not in keywords:
            keywords.append(token)

    severity_score = min(5.0, round(primary_rule["severity"] + ((3.0 - rating) * 0.35), 2))
    confidence = 0.55 + (0.08 * len(candidates)) + (0.04 * min(len(surface_terms), 4))
    confidence = round(min(confidence, 0.95), 2)

    return {
        **review_row,
        "emotion_major": primary_rule["emotion_major"],
        "emotion_type": primary_rule["emotion_type"],
        "journey_stage": primary_rule["journey_stage"],
        "appeals_l1": primary_rule["appeals_l1"],
        "appeals_l2": primary_rule["appeals_l2"],
        "appeals_type": f"{primary_rule['appeals_l1']} / {primary_rule['appeals_l2']}",
        "emotion_reason": primary_rule["reason"],
        "keyword_list": keywords[:6],
        "keyword_text": " / ".join(keywords[:6]) if keywords else "体验不及预期",
        "chinese_interpretation": compose_chinese_interpretation(primary_rule, surface_terms),
        "improvement_suggestion": primary_rule["improvement"],
        "unmet_need": primary_rule["unmet_need"],
        "severity_score": severity_score,
        "severity_label": severity_label(severity_score),
        "confidence": confidence,
        "matched_dimensions": related_dimensions,
    }


def find_product_payload(asin_dir: Path, asin: str) -> dict[str, Any]:
    candidates = [asin_dir / f"{asin}-product.json", *sorted(asin_dir.glob("*product*.json"))]
    for path in candidates:
        if path.exists():
            payload = load_json(path)
            if isinstance(payload, dict):
                return payload
    return {}


def find_review_files(asin_dir: Path, asin: str) -> list[Path]:
    files: list[Path] = []
    for pattern in REVIEW_FILE_PRIORITY:
        candidate = asin_dir / pattern.format(asin=asin)
        if candidate.exists():
            files.append(candidate)

    for candidate in sorted(asin_dir.glob("*reviews*.json")):
        name = candidate.name.lower()
        if "meta" in name or "product" in name:
            continue
        if candidate not in files:
            files.append(candidate)
    return files


def collect_review_voice_pool(base_dir: str | Path = DEFAULT_BASE_DIR) -> list[dict[str, Any]]:
    base_path = Path(base_dir)
    voice_pool = []
    seen = set()

    for asin_dir in sorted(path for path in base_path.iterdir() if path.is_dir() and path.name.upper().startswith("B")):
        asin = asin_dir.name
        product = find_product_payload(asin_dir, asin)
        product_title = normalize_space(
            first_non_empty(
                product.get("title"),
                product.get("name"),
                product.get("product_title"),
                product.get("productName"),
                asin,
            )
        )
        brand = infer_brand(product_title, str(first_non_empty(product.get("brand"), "")))
        review_files = find_review_files(asin_dir, asin)

        for review_file in review_files:
            for raw_review in flatten_review_payload(load_json(review_file)):
                text = normalize_review_text(raw_review)
                rating = parse_rating(
                    first_non_empty(
                        raw_review.get("rating"),
                        raw_review.get("r"),
                        raw_review.get("stars"),
                        raw_review.get("ratingScore"),
                    )
                )
                if not text or rating is None or rating > 3:
                    continue

                review_date = parse_review_date(
                    first_non_empty(
                        raw_review.get("date"),
                        raw_review.get("reviewDate"),
                        raw_review.get("reviewedIn"),
                        raw_review.get("created_at"),
                    )
                )
                dedupe_key = "|".join(
                    [
                        asin,
                        f"{rating:.1f}",
                        text.lower(),
                        review_date.isoformat() if review_date else "",
                    ]
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                row = {
                    "asin": asin,
                    "brand": brand,
                    "product_title": product_title,
                    "price": parse_price(first_non_empty(product.get("price"), raw_review.get("price"))),
                    "rating": float(rating),
                    "review_date": review_date,
                    "date_raw": str(
                        first_non_empty(
                            raw_review.get("date"),
                            raw_review.get("reviewDate"),
                            raw_review.get("reviewedIn"),
                            "",
                        )
                    ),
                    "original_text": text,
                    "source_file": review_file.name,
                }
                voice_pool.append(annotate_review(row))

    voice_pool.sort(
        key=lambda item: (
            -item["severity_score"],
            item["review_date"] or dt.date.min,
            item["asin"],
        ),
        reverse=False,
    )
    return voice_pool


def top_terms(rows: list[dict[str, Any]], limit: int = 5) -> list[str]:
    counts = Counter()
    for row in rows:
        counts.update(row["keyword_list"])
    return [term for term, _ in counts.most_common(limit)]


def representative_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        rows,
        key=lambda item: (
            item["severity_score"],
            item["confidence"],
            len(item["original_text"]),
        ),
    )


def build_emotion_summary(voice_pool: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    total = len(voice_pool) or 1
    by_major = defaultdict(list)
    by_type = defaultdict(list)

    for row in voice_pool:
        by_major[row["emotion_major"]].append(row)
        by_type[(row["emotion_major"], row["emotion_type"])].append(row)

    major_rows = []
    for emotion in EMOTION_ORDER:
        rows = by_major.get(emotion, [])
        if not rows:
            continue
        major_rows.append(
            {
                "emotion_major": emotion,
                "count": len(rows),
                "share": round(len(rows) / total, 4),
                "color": EMOTION_COLORS.get(emotion, "#64748b"),
            }
        )

    type_rows = []
    for (emotion_major, emotion_type), rows in sorted(by_type.items(), key=lambda item: len(item[1]), reverse=True):
        rep = representative_row(rows)
        type_rows.append(
            {
                "emotion_major": emotion_major,
                "emotion_type": emotion_type,
                "count": len(rows),
                "share": round(len(rows) / total, 4),
                "reason": Counter(row["emotion_reason"] for row in rows).most_common(1)[0][0],
                "keywords": top_terms(rows, limit=4),
                "representative_comment": rep["original_text"],
                "representative_cn": rep["chinese_interpretation"],
            }
        )
    return major_rows, type_rows


def build_journey_summary(voice_pool: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    total = len(voice_pool) or 1
    by_stage = defaultdict(list)
    matrix = {stage: {emotion: 0 for emotion in EMOTION_ORDER} for stage in STAGE_ORDER}

    for row in voice_pool:
        by_stage[row["journey_stage"]].append(row)
        matrix.setdefault(row["journey_stage"], {emotion: 0 for emotion in EMOTION_ORDER})
        matrix[row["journey_stage"]][row["emotion_major"]] += 1

    summary = []
    for stage in STAGE_ORDER:
        rows = by_stage.get(stage, [])
        if not rows:
            continue
        rep = representative_row(rows)
        summary.append(
            {
                "journey_stage": stage,
                "count": len(rows),
                "share": round(len(rows) / total, 4),
                "top_emotions": [name for name, _ in Counter(row["emotion_major"] for row in rows).most_common(2)],
                "top_appeals": [name for name, _ in Counter(row["appeals_l1"] for row in rows).most_common(2)],
                "unmet_need": Counter(row["unmet_need"] for row in rows).most_common(1)[0][0],
                "representative_comment": rep["original_text"],
                "representative_cn": rep["chinese_interpretation"],
            }
        )
    return summary, matrix


def build_appeals_summaries(voice_pool: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    total = len(voice_pool) or 1
    by_l1 = defaultdict(list)
    by_l2 = defaultdict(list)

    for row in voice_pool:
        by_l1[row["appeals_l1"]].append(row)
        by_l2[(row["appeals_l1"], row["appeals_l2"])].append(row)

    l1_rows = []
    for dimension, rows in sorted(by_l1.items(), key=lambda item: len(item[1]), reverse=True):
        rep = representative_row(rows)
        l1_rows.append(
            {
                "appeals_l1": dimension,
                "count": len(rows),
                "share": round(len(rows) / total, 4),
                "avg_severity": round(sum(row["severity_score"] for row in rows) / len(rows), 2),
                "top_keywords": top_terms(rows, limit=5),
                "top_reason": Counter(row["emotion_reason"] for row in rows).most_common(1)[0][0],
                "representative_comment": rep["original_text"],
                "representative_cn": rep["chinese_interpretation"],
                "color": APPEALS_COLORS.get(dimension, "#64748b"),
            }
        )

    l2_rows = []
    for (dimension, issue), rows in sorted(by_l2.items(), key=lambda item: len(item[1]), reverse=True):
        rep = representative_row(rows)
        journey_span = len({row["journey_stage"] for row in rows})
        emotion_span = len({row["emotion_major"] for row in rows})
        avg_severity = round(sum(row["severity_score"] for row in rows) / len(rows), 2)
        priority_score = round((len(rows) * 7.5) + (avg_severity * 8) + (journey_span * 4) + (emotion_span * 2), 1)
        is_fallback = issue == DEFAULT_RULE["appeals_l2"]
        if is_fallback:
            priority_score = round(priority_score * 0.18, 1)
        l2_rows.append(
            {
                "appeals_l1": dimension,
                "appeals_l2": issue,
                "appeals_type": f"{dimension} / {issue}",
                "count": len(rows),
                "share": round(len(rows) / total, 4),
                "avg_severity": avg_severity,
                "priority_score": priority_score,
                "top_emotion_major": Counter(row["emotion_major"] for row in rows).most_common(1)[0][0],
                "top_emotion_type": Counter(row["emotion_type"] for row in rows).most_common(1)[0][0],
                "emotion_reason": Counter(row["emotion_reason"] for row in rows).most_common(1)[0][0],
                "top_keywords": top_terms(rows, limit=5),
                "improvement_suggestion": Counter(row["improvement_suggestion"] for row in rows).most_common(1)[0][0],
                "unmet_need": Counter(row["unmet_need"] for row in rows).most_common(1)[0][0],
                "representative_comment": rep["original_text"],
                "representative_cn": rep["chinese_interpretation"],
                "evidence_rows": rows,
                "color": APPEALS_COLORS.get(dimension, "#64748b"),
                "is_fallback": is_fallback,
            }
        )
    l2_rows.sort(key=lambda item: (item["is_fallback"], -item["priority_score"], -item["count"]))
    return l1_rows, l2_rows


def build_report_tables(voice_pool: list[dict[str, Any]]) -> dict[str, Any]:
    emotion_major_summary, emotion_type_summary = build_emotion_summary(voice_pool)
    journey_summary, journey_matrix = build_journey_summary(voice_pool)
    appeals_l1_summary, appeals_l2_summary = build_appeals_summaries(voice_pool)
    ppi_summary = build_pain_pleasure_itch_summary(voice_pool)

    keyword_counter = Counter()
    for row in voice_pool:
        keyword_counter.update(row["keyword_list"])

    source_products = sorted(
        {
            (row["asin"], row["brand"], row["product_title"])
            for row in voice_pool
        }
    )

    ranked_issues = [row for row in appeals_l2_summary if not row["is_fallback"]] or appeals_l2_summary

    issue_table = []
    for row in ranked_issues[:8]:
        issue_table.append(
            {
                "emotion_major": row["top_emotion_major"],
                "emotion_type": row["top_emotion_type"],
                "focus_count": row["count"],
                "appeals_type": row["appeals_type"],
                "emotion_reason": row["emotion_reason"],
                "keywords": row["top_keywords"],
                "improvement": row["improvement_suggestion"],
                "representative_comment": row["representative_comment"],
                "representative_cn": row["representative_cn"],
            }
        )

    recommendations = []
    for row in ranked_issues[:3]:
        recommendations.append(
            {
                "title": row["appeals_l2"],
                "dimension": row["appeals_l1"],
                "priority_score": row["priority_score"],
                "why": row["emotion_reason"],
                "action": row["improvement_suggestion"],
                "impact": row["unmet_need"],
            }
        )

    return {
        "voice_pool": voice_pool,
        "emotion_major_summary": emotion_major_summary,
        "emotion_type_summary": emotion_type_summary,
        "journey_summary": journey_summary,
        "journey_matrix": journey_matrix,
        "appeals_l1_summary": appeals_l1_summary,
        "appeals_l2_summary": appeals_l2_summary,
        "pain_pleasure_itch_summary": ppi_summary,
        "ranked_issues": ranked_issues,
        "issue_table": issue_table,
        "recommendations": recommendations,
        "keyword_counter": keyword_counter,
        "source_products": source_products,
        "source_product_count": len(source_products),
        "review_count": len(voice_pool),
        "low_star_only": all((row.get("rating") or 0) <= 3 for row in voice_pool),
        "journey_stage_count": len(journey_summary),
        "appeals_dimension_count": len(appeals_l1_summary),
    }


def percentage(value: float) -> str:
    return f"{value * 100:.1f}%"


def escape(value: Any) -> str:
    return html.escape(str(value))


def build_timestamped_output_path(
    extension: str,
    output_dir: str | Path | None = None,
    generated_at: dt.datetime | None = None,
) -> Path:
    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    timestamp = (generated_at or dt.datetime.now()).strftime("%Y%m%d-%H%M%S")
    base_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    return base_dir / f"report-{timestamp}{normalized_extension}"


def render_bar_chart(rows: list[dict[str, Any]], label_key: str, value_key: str, color_key: str) -> str:
    if not rows:
        return "<div class='empty'>暂无数据</div>"
    max_value = max(row[value_key] for row in rows) or 1
    parts = ["<div class='bar-chart'>"]
    for row in rows:
        width = max(8, round((row[value_key] / max_value) * 100, 1))
        parts.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{escape(row[label_key])}</div>
              <div class="bar-track">
                <div class="bar-fill" style="width:{width}%;background:{escape(row[color_key])};"></div>
              </div>
              <div class="bar-value">{row[value_key]} / {percentage(row['share'])}</div>
            </div>
            """
        )
    parts.append("</div>")
    return "".join(parts)


def render_donut_chart(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class='empty'>暂无数据</div>"
    total = sum(row["count"] for row in rows) or 1
    angle = 0.0
    segments = []
    legend = []
    for row in rows:
        slice_share = (row["count"] / total) * 100
        next_angle = angle + slice_share
        color = EMOTION_COLORS.get(row["emotion_major"], "#64748b")
        segments.append(f"{color} {angle:.2f}% {next_angle:.2f}%")
        legend.append(
            f"<div class='legend-item'><span class='swatch' style='background:{color};'></span>"
            f"{escape(row['emotion_type'])} <strong>{row['count']}</strong> <span>{percentage(row['share'])}</span></div>"
        )
        angle = next_angle
    donut_style = ";".join(
        [
            f"--donut: conic-gradient({', '.join(segments)})",
        ]
    )
    return f"""
    <div class="donut-wrap">
      <div class="donut" style="{donut_style}"></div>
      <div class="legend">{''.join(legend)}</div>
    </div>
    """


def render_stage_matrix(matrix: dict[str, dict[str, int]]) -> str:
    rows = []
    for stage in STAGE_ORDER:
        if stage not in matrix:
            continue
        cells = "".join(f"<td>{matrix[stage].get(emotion, 0)}</td>" for emotion in EMOTION_ORDER)
        rows.append(f"<tr><th>{escape(stage)}</th>{cells}</tr>")
    if not rows:
        return "<div class='empty'>暂无数据</div>"
    header = "".join(f"<th>{escape(emotion)}</th>" for emotion in EMOTION_ORDER)
    return f"""
    <table class="matrix-table">
      <thead><tr><th>旅程阶段</th>{header}</tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


def render_bubble_chart(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class='empty'>暂无数据</div>"

    top_rows = rows[:8]
    max_share = max(row["share"] for row in top_rows) or 0.01
    max_priority = max(row["priority_score"] for row in top_rows) or 1
    bubbles = []
    labels = []

    for row in top_rows:
        x = 70 + ((row["share"] / max_share) * 500)
        y = 265 - (((row["avg_severity"] - 1.0) / 4.0) * 195)
        radius = 12 + ((row["priority_score"] / max_priority) * 18)
        color = row["color"]
        short_label = truncate(row["appeals_l2"], 12)
        bubbles.append(
            f"<circle cx='{x:.1f}' cy='{y:.1f}' r='{radius:.1f}' fill='{color}' fill-opacity='0.72' stroke='{color}' stroke-width='1.5'></circle>"
        )
        labels.append(
            f"<text x='{x:.1f}' y='{y + radius + 14:.1f}' text-anchor='middle'>{escape(short_label)}</text>"
        )

    grid_lines = []
    for severity in range(1, 6):
        y = 265 - (((severity - 1.0) / 4.0) * 195)
        grid_lines.append(
            f"<line x1='60' y1='{y:.1f}' x2='590' y2='{y:.1f}' stroke='#e5e7eb' stroke-width='1'></line>"
            f"<text x='38' y='{y + 4:.1f}' text-anchor='end'>{severity}</text>"
        )
    for share_tick in range(0, 6):
        x = 70 + (share_tick * 100)
        label = f"{(max_share * share_tick / 5) * 100:.0f}%"
        grid_lines.append(
            f"<line x1='{x:.1f}' y1='40' x2='{x:.1f}' y2='270' stroke='#f1f5f9' stroke-width='1'></line>"
            f"<text x='{x:.1f}' y='292' text-anchor='middle'>{label}</text>"
        )

    return f"""
    <svg class="bubble-chart" viewBox="0 0 640 320" role="img" aria-label="APPEALS 二级问题优先级气泡图">
      <style>
        .bubble-chart text {{ fill:#475569; font-size:11px; font-family:"PingFang SC","Noto Sans SC",sans-serif; }}
      </style>
      <rect x="0" y="0" width="640" height="320" fill="#ffffff"></rect>
      {''.join(grid_lines)}
      <line x1="60" y1="270" x2="600" y2="270" stroke="#94a3b8" stroke-width="1.5"></line>
      <line x1="60" y1="40" x2="60" y2="270" stroke="#94a3b8" stroke-width="1.5"></line>
      <text x="610" y="292" text-anchor="end">样本占比</text>
      <text x="28" y="28">严重度</text>
      {''.join(bubbles)}
      {''.join(labels)}
    </svg>
    """


def render_keyword_cloud(counter: Counter[str]) -> str:
    if not counter:
        return "<div class='empty'>暂无数据</div>"
    most_common = counter.most_common(24)
    max_count = most_common[0][1] or 1
    chips = []
    for word, count in most_common:
        size = 12 + int((count / max_count) * 14)
        chips.append(f"<span class='keyword-chip' style='font-size:{size}px'>{escape(word)} <small>{count}</small></span>")
    return f"<div class='keyword-cloud'>{''.join(chips)}</div>"


def render_ppi_cards(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class='empty'>暂无数据</div>"
    cards = []
    for row in rows:
        cards.append(
            f"""
            <div class="ppi-card">
              <div class="ppi-badge">{escape(row['need_dimension'])}</div>
              <div class="ppi-meta">{escape(row['matrix_quadrant'])} ｜ 占比 {percentage(row['share'])}</div>
              <p class="ppi-body">{escape(row['opportunity_statement'])}</p>
              <p class="ppi-user">用户状态：{escape(row['user_state'])}</p>
              <p class="ppi-strategy">产品策略：{escape(row['product_strategy'])}</p>
              <div class="ppi-evidence">
                <div class="quote-compact">{escape(truncate(row['representative_comment'], 110))}</div>
                <div class="quote-translation">{escape(truncate(row['representative_cn'], 90))}</div>
              </div>
            </div>
            """
        )
    return f"<div class='ppi-grid'>{''.join(cards)}</div>"


def render_ppi_cards(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class='empty'>暂无数据</div>"
    cards = []
    for row in rows:
        cards.append(
            f"""
            <div class="ppi-card">
              <div class="ppi-badge">{escape(row['need_dimension'])}</div>
              <div class="ppi-meta">{escape(row['matrix_quadrant'])} ｜ 占比 {percentage(row['share'])}</div>
              <p class="ppi-body">{escape(row['opportunity_statement'])}</p>
              <p class="ppi-user">用户状态：{escape(row['user_state'])}</p>
              <p class="ppi-strategy">产品策略：{escape(row['product_strategy'])}</p>
              <div class="ppi-evidence">
                <div class="quote-compact">{escape(truncate(row['representative_comment'], 110))}</div>
                <div class="quote-translation">{escape(truncate(row['representative_cn'], 90))}</div>
              </div>
            </div>
            """
        )
    return f"<div class='ppi-grid'>{''.join(cards)}</div>"


def render_issue_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class='empty'>暂无数据</div>"
    body = []
    for row in rows:
        body.append(
            f"""
            <tr>
              <td>{escape(row['emotion_major'])}</td>
              <td>{escape(row['emotion_type'])}</td>
              <td>{row['focus_count']}</td>
              <td>{escape(row['appeals_type'])}</td>
              <td>{escape(row['emotion_reason'])}</td>
              <td>{escape(' / '.join(row['keywords']))}</td>
              <td>{escape(row['improvement'])}</td>
              <td>
                <div class="quote-compact">{escape(truncate(row['representative_comment'], 88))}</div>
                <div class="quote-translation">{escape(truncate(row['representative_cn'], 72))}</div>
              </td>
            </tr>
            """
        )
    return f"""
    <table>
      <thead>
        <tr>
          <th>情绪大类</th>
          <th>情绪类型</th>
          <th>聚焦量</th>
          <th>$APPEALS 类型</th>
          <th>产生情绪的原因</th>
          <th>关键词</th>
          <th>改进建议</th>
          <th>代表评论</th>
        </tr>
      </thead>
      <tbody>{''.join(body)}</tbody>
    </table>
    """


def render_summary_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return "<div class='empty'>暂无数据</div>"
    header = "".join(f"<th>{escape(title)}</th>" for title, _ in columns)
    body_rows = []
    for row in rows:
        cells = []
        for _, key in columns:
            value = row[key]
            if isinstance(value, list):
                value = " / ".join(str(item) for item in value)
            elif isinstance(value, float) and 0 <= value <= 1:
                value = percentage(value)
            cells.append(f"<td>{escape(value)}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def render_recommendation_cards(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class='empty'>暂无数据</div>"
    cards = []
    for index, row in enumerate(rows, start=1):
        color = APPEALS_COLORS.get(row["dimension"], "#2563eb")
        cards.append(
            f"""
            <div class="recommend-card" style="border-top-color:{color};">
              <div class="recommend-rank">Top {index}</div>
              <h3>{escape(row['title'])}</h3>
              <p><strong>{escape(row['dimension'])}</strong> ｜ 优先级分数 {row['priority_score']}</p>
              <p>{escape(row['why'])}</p>
              <p><strong>怎么改：</strong>{escape(row['action'])}</p>
              <p><strong>背后需求：</strong>{escape(row['impact'])}</p>
            </div>
            """
        )
    return f"<div class='recommend-grid'>{''.join(cards)}</div>"


def render_ppi_section(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class='empty'>暂无数据</div>"
    quadrants = defaultdict(list)
    for row in rows:
        quadrants[row["matrix_quadrant"]].append(row)
    chips = []
    for quadrant, items in quadrants.items():
        share = sum(item["share"] for item in items)
        chips.append(f"<span class='pill'>{escape(quadrant)} ｜ {percentage(share)}</span>")
    return "".join(
        [
            "<div class='pill-wrap'>",
            "".join(chips),
            "</div>",
            render_ppi_cards(rows),
        ]
    )


def render_evidence_rows(voice_pool: list[dict[str, Any]]) -> str:
    rows = []
    for row in voice_pool:
        search_blob = " ".join(
            [
                row["asin"],
                row["brand"],
                row["product_title"],
                row["appeals_l1"],
                row["appeals_l2"],
                row["emotion_major"],
                row["emotion_type"],
                row["journey_stage"],
                row["keyword_text"],
                row["original_text"],
                row["chinese_interpretation"],
            ]
        ).lower()
        rows.append(
            f"""
            <tr class="evidence-row" data-search="{escape(search_blob)}" data-dimension="{escape(row['appeals_l1'])}">
              <td>
                <div><strong>{escape(row['asin'])}</strong></div>
                <div class="muted">{escape(row['brand'])}</div>
                <div class="muted">{escape(truncate(row['product_title'], 48))}</div>
              </td>
              <td>{escape(row['appeals_type'])}</td>
              <td>{escape(row['emotion_major'])} / {escape(row['emotion_type'])}</td>
              <td>{escape(row['journey_stage'])}</td>
              <td>{escape(row['keyword_text'])}</td>
              <td>{escape(truncate(row['original_text'], 140))}</td>
              <td>{escape(truncate(row['chinese_interpretation'], 96))}</td>
              <td>{row['confidence']:.2f}</td>
            </tr>
            """
        )
    return "".join(rows)


def build_intro_text(tables: dict[str, Any]) -> tuple[str, str]:
    review_count = tables["review_count"]
    source_count = tables["source_product_count"]
    top_issue = tables["ranked_issues"][0] if tables["ranked_issues"] else None
    top_emotion = max(tables["emotion_major_summary"], key=lambda row: row["count"], default=None)
    top_stage = max(tables["journey_summary"], key=lambda row: row["count"], default=None)

    if not top_issue:
        one_liner = "当前目录下没有可用于聚合的低星评论样本，无法生成稳定的同品类差评分析。"
        note = "请确认每个 ASIN 目录下存在 reviews JSON，且评论带有 rating 与 body/text 字段。"
        return one_liner, note

    one_liner = (
        f"这份报告基于 {source_count} 个同品类来源产品、{review_count} 条低星评论样本做聚合分析。"
        f"当前最集中的问题是“{top_issue['appeals_l2']}”，主导情绪为“{top_emotion['emotion_major']}”，"
        f"高频爆发环节集中在“{top_stage['journey_stage']}”。"
    )
    note = (
        "所有占比均表示“在当前低星样本中的分布占比”，不代表全量评论正负比。"
        " 当前版本将多个 ASIN 视为同种产品样本池，前台不做品牌或 ASIN 胜负对比。"
    )
    return one_liner, note


def build_html_report(base_dir: str | Path, tables: dict[str, Any]) -> str:
    base_path = Path(base_dir)
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    one_liner, note = build_intro_text(tables)
    top_l1 = tables["appeals_l1_summary"][0]["appeals_l1"] if tables["appeals_l1_summary"] else "暂无"
    emotion_table = render_summary_table(
        tables["emotion_type_summary"][:8],
        [
            ("情绪大类", "emotion_major"),
            ("情绪类型", "emotion_type"),
            ("聚焦量", "count"),
            ("占比", "share"),
            ("主要原因", "reason"),
            ("关键词", "keywords"),
        ],
    )
    journey_table = render_summary_table(
        tables["journey_summary"],
        [
            ("旅程阶段", "journey_stage"),
            ("问题量", "count"),
            ("占比", "share"),
            ("关联情绪", "top_emotions"),
            ("关联 APPEALS", "top_appeals"),
            ("未被满足的需求", "unmet_need"),
        ],
    )

    dimension_options = ["<option value=''>全部维度</option>"]
    for row in tables["appeals_l1_summary"]:
        dimension_options.append(f"<option value='{escape(row['appeals_l1'])}'>{escape(row['appeals_l1'])}</option>")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>同品类差评聚合 $APPEALS HTML 报告</title>
  <style>
    :root {{
      --bg: #f4f6f8;
      --card: #ffffff;
      --line: #d9e2ec;
      --text: #1f2937;
      --muted: #66758a;
      --soft: #f8fafc;
      --accent: #2563eb;
      --warn: #fff7ed;
      --good: #eef6ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.55;
    }}
    .page {{
      max-width: 1460px;
      margin: 0 auto;
      padding: 24px 24px 48px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px 18px;
    }}
    .header {{
      display: grid;
      grid-template-columns: 1.7fr 1fr;
      gap: 16px;
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      line-height: 1.2;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 20px;
    }}
    h3 {{
      margin: 0 0 8px;
      font-size: 16px;
    }}
    p {{
      margin: 0 0 10px;
    }}
    .meta {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 10px;
    }}
    .section {{
      margin-top: 16px;
    }}
    .grid-2 {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .grid-3 {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .pill-wrap {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-content: start;
    }}
    .pill {{
      border: 1px solid #c8d7e6;
      background: var(--good);
      color: #1d4ed8;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 13px;
      white-space: nowrap;
    }}
    .sample-note {{
      background: var(--warn);
      border-color: #fed7aa;
    }}
    .muted {{
      color: var(--muted);
      font-size: 13px;
    }}
    .bar-chart {{
      display: grid;
      gap: 10px;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: 120px 1fr 92px;
      gap: 10px;
      align-items: center;
    }}
    .bar-label {{
      font-size: 13px;
      color: var(--muted);
    }}
    .bar-track {{
      height: 12px;
      border-radius: 999px;
      background: #eef2f7;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      border-radius: 999px;
    }}
    .bar-value {{
      font-size: 12px;
      color: var(--muted);
      text-align: right;
    }}
    .donut-wrap {{
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 16px;
      align-items: center;
    }}
    .donut {{
      width: 180px;
      height: 180px;
      border-radius: 50%;
      background: var(--donut);
      position: relative;
      margin: 0 auto;
    }}
    .donut::after {{
      content: "";
      position: absolute;
      inset: 32px;
      background: white;
      border-radius: 50%;
      border: 1px solid var(--line);
    }}
    .legend {{
      display: grid;
      gap: 8px;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: var(--muted);
    }}
    .swatch {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      flex: 0 0 auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: white;
      border: 1px solid var(--line);
      border-radius: 14px;
      overflow: hidden;
      font-size: 13px;
    }}
    th, td {{
      text-align: left;
      padding: 10px 11px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{
      background: #f8fafc;
      font-weight: 600;
    }}
    tr:last-child td {{
      border-bottom: none;
    }}
    .matrix-table th:first-child,
    .matrix-table td:first-child {{
      white-space: nowrap;
    }}
    .keyword-cloud {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }}
    .keyword-chip {{
      background: #f1f5f9;
      border: 1px solid #d9e2ec;
      border-radius: 999px;
      padding: 6px 10px;
      color: #334155;
      line-height: 1.1;
    }}
    .keyword-chip small {{
      color: var(--muted);
      font-size: 11px;
    }}
    .recommend-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .recommend-card {{
      background: white;
      border: 1px solid var(--line);
      border-top: 4px solid var(--accent);
      border-radius: 14px;
      padding: 14px 16px;
    }}
    .ppi-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .ppi-card {{
      background: white;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px 16px;
    }}
    .ppi-badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      background: #eef2ff;
      color: #4338ca;
      font-size: 12px;
      margin-bottom: 6px;
    }}
    .ppi-meta {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }}
    .ppi-body {{ margin: 0 0 8px; }}
    .ppi-user, .ppi-strategy {{
      margin: 0 0 6px;
      color: #111827;
      font-size: 13px;
    }}
    .ppi-evidence {{ margin-top: 8px; }}
    .recommend-rank {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }}
    .quote-compact {{
      color: #111827;
      margin-bottom: 4px;
    }}
    .quote-translation {{
      color: var(--muted);
      font-size: 12px;
    }}
    .bubble-chart {{
      width: 100%;
      height: auto;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: white;
    }}
    .appendix-controls {{
      display: grid;
      grid-template-columns: 1fr 220px;
      gap: 12px;
      margin-bottom: 12px;
    }}
    .appendix-controls input,
    .appendix-controls select {{
      width: 100%;
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid #cbd5e1;
      background: #fff;
      font: inherit;
    }}
    .evidence-shell {{
      overflow-x: auto;
    }}
    .empty {{
      color: var(--muted);
      font-size: 13px;
      padding: 10px 0;
    }}
    @media (max-width: 1100px) {{
      .header,
      .grid-2,
      .grid-3,
      .recommend-grid,
      .appendix-controls,
      .donut-wrap {{
        grid-template-columns: 1fr;
      }}
      .bar-row {{
        grid-template-columns: 96px 1fr 70px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="header">
      <div class="card">
        <h1>同品类差评聚合 $APPEALS HTML 报告</h1>
        <div class="meta">生成时间：{escape(generated_at)} ｜ 数据目录：{escape(base_path)} ｜ 视角：聚合同品类低星评论</div>
        <p>{escape(one_liner)}</p>
        <p class="muted">{escape(note)}</p>
      </div>
      <div class="card sample-note">
        <div class="pill-wrap">
          <span class="pill">来源产品数：{tables['source_product_count']}</span>
          <span class="pill">差评样本：{tables['review_count']}</span>
          <span class="pill">旅程阶段：{tables['journey_stage_count']}</span>
          <span class="pill">命中维度：{tables['appeals_dimension_count']}</span>
          <span class="pill">主导维度：{escape(top_l1)}</span>
        </div>
        <p style="margin-top:12px;"><strong>当前样本说明</strong></p>
        <p class="muted">本报告按低星评论聚合生成，因此所有图表和表格只反映差评样本内部的分布。HTML 前台不做 ASIN 横向 PK，来源信息统一放在证据附录。</p>
      </div>
    </div>

    <section class="section">
      <div class="card">
        <h2>用户情绪分析</h2>
        <div class="grid-2">
          <div>
            <h3>情绪大类分布</h3>
            {render_bar_chart(tables['emotion_major_summary'], 'emotion_major', 'count', 'color')}
          </div>
          <div>
            <h3>情绪类型占比</h3>
            {render_donut_chart(tables['emotion_type_summary'][:6])}
          </div>
        </div>
        <div style="margin-top:14px;">
          {emotion_table}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="card">
        <h2>用户旅程分析</h2>
        <div class="grid-2">
          <div>
            <h3>旅程阶段问题量</h3>
            {render_bar_chart(
                [
                    {
                        'journey_stage': row['journey_stage'],
                        'count': row['count'],
                        'share': row['share'],
                        'color': '#0f766e',
                    }
                    for row in tables['journey_summary']
                ],
                'journey_stage',
                'count',
                'color',
            )}
          </div>
          <div>
            <h3>旅程阶段 × 情绪矩阵</h3>
            {render_stage_matrix(tables['journey_matrix'])}
          </div>
        </div>
        <div style="margin-top:14px;">
          {journey_table}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="card">
        <h2>$APPEALS 需求满意度分析</h2>
        <div class="grid-2">
          <div>
            <h3>一级维度聚焦量</h3>
            {render_bar_chart(tables['appeals_l1_summary'], 'appeals_l1', 'count', 'color')}
          </div>
          <div>
            <h3>二级问题优先级气泡图</h3>
            {render_bubble_chart(tables['appeals_l2_summary'])}
          </div>
        </div>
        <div class="section">
          <h3>关键词聚类</h3>
          {render_keyword_cloud(tables['keyword_counter'])}
        </div>
        <div class="section">
          {render_issue_table(tables['issue_table'])}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="card">
        <h2>痛点-爽点-痒点矩阵</h2>
        <p class="muted">依据严重度与样本占比推断痛点强度与使用频率，映射到刚需/爽点/痒点象限。</p>
        {render_ppi_section(tables['pain_pleasure_itch_summary'])}
      </div>
    </section>

    <section class="section">
      <div class="card">
        <h2>改进建议</h2>
        <p class="muted">以下优先级基于问题频次、平均严重度、跨旅程影响面和情绪扩散度综合计算。</p>
        {render_recommendation_cards(tables['recommendations'])}
      </div>
    </section>

    <section class="section">
      <div class="card">
        <h2>证据附录</h2>
        <p class="muted">保留英文原文与中文解读，支持按关键词或 $APPEALS 维度定位证据。来源 ASIN、品牌和产品名只在本区展示。</p>
        <div class="appendix-controls">
          <input id="evidence-search" type="search" placeholder="搜索关键词、评论原文、中文解读、ASIN、品牌或阶段" />
          <select id="evidence-dimension">{''.join(dimension_options)}</select>
        </div>
        <div class="evidence-shell">
          <table>
            <thead>
              <tr>
                <th>来源产品</th>
                <th>$APPEALS</th>
                <th>情绪</th>
                <th>旅程阶段</th>
                <th>关键词</th>
                <th>英文原文</th>
                <th>中文解读</th>
                <th>置信度</th>
              </tr>
            </thead>
            <tbody>
              {render_evidence_rows(tables['voice_pool'])}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>

  <script>
    (function() {{
      const searchInput = document.getElementById('evidence-search');
      const dimensionSelect = document.getElementById('evidence-dimension');
      const rows = Array.from(document.querySelectorAll('.evidence-row'));

      function filterRows() {{
        const query = (searchInput.value || '').trim().toLowerCase();
        const dimension = dimensionSelect.value;
        rows.forEach((row) => {{
          const haystack = row.dataset.search || '';
          const matchesQuery = !query || haystack.includes(query);
          const matchesDimension = !dimension || row.dataset.dimension === dimension;
          row.style.display = matchesQuery && matchesDimension ? '' : 'none';
        }});
      }}

      searchInput.addEventListener('input', filterRows);
      dimensionSelect.addEventListener('change', filterRows);
    }})();
  </script>
</body>
</html>
"""


def write_html_report(base_dir: str | Path, tables: dict[str, Any], output_path: str | Path) -> Path:
    base_path = Path(base_dir)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html_report(base_path, tables), encoding="utf-8")
    return output


def generate_report(base_dir: str | Path = DEFAULT_BASE_DIR, output_path: str | Path | None = None) -> Path:
    base_path = Path(base_dir)
    if output_path is None:
        output_path = build_timestamped_output_path("html")
    tables = build_report_tables(collect_review_voice_pool(base_path))
    return write_html_report(base_path, tables, output_path)


def generate_report_bundle(
    base_dir: str | Path = DEFAULT_BASE_DIR,
    output_path: str | Path | None = None,
    excel_output_path: str | Path | None = None,
    output_format: str = "both",
    evidence_limit: int | None = None,
) -> dict[str, Path]:
    base_path = Path(base_dir)
    generated_at = dt.datetime.now()
    html_path = Path(output_path) if output_path else build_timestamped_output_path("html", generated_at=generated_at)
    xlsx_path = Path(excel_output_path) if excel_output_path else build_timestamped_output_path("xlsx", generated_at=generated_at)
    tables = build_report_tables(collect_review_voice_pool(base_path))
    outputs: dict[str, Path] = {}

    if output_format in {"both", "html"}:
        outputs["html"] = write_html_report(base_path, tables, html_path)

    if output_format in {"both", "excel"}:
        from export_appeals_excel import export_excel

        outputs["excel"] = export_excel(
            base_dir=base_path,
            output_path=xlsx_path,
            tables=tables,
            evidence_limit=evidence_limit,
        )

    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate same-category APPEALS reports from Amazon review folders.")
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR), help="Directory containing ASIN subfolders.")
    parser.add_argument("--output", default="", help="Path to the generated HTML file. Defaults to output/report-<timestamp>.html.")
    parser.add_argument("--excel-output", default="", help="Path to the generated Excel workbook. Defaults to output/report-<timestamp>.xlsx.")
    parser.add_argument("--format", choices=("both", "html", "excel"), default="both", help="Output format to generate.")
    parser.add_argument("--evidence-limit", type=int, default=None, help="Optional evidence row limit for the Excel appendix.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = generate_report_bundle(
        base_dir=args.base_dir,
        output_path=args.output or None,
        excel_output_path=args.excel_output or None,
        output_format=args.format,
        evidence_limit=args.evidence_limit,
    )
    if "html" in outputs:
        print(f"HTML report written to: {outputs['html']}")
    if "excel" in outputs:
        print(f"Excel workbook written to: {outputs['excel']}")


if __name__ == "__main__":
    main()
