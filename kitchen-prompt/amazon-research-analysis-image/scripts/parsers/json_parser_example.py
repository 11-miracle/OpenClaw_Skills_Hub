#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import build_record, ensure_parent_dir, write_jsonl


TEXT_HINTS = ("text", "comment", "review", "content", "body", "message", "feedback", "note", "description")
TITLE_HINTS = ("title", "subject", "heading", "name")


def load_payload(input_path: Path) -> list[Any]:
    if input_path.suffix.lower() == ".jsonl":
        items = []
        with input_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
        return items

    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "records", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return [payload]
    raise SystemExit("Unsupported JSON structure. Expected a list or object.")


def choose_text(item: dict[str, Any]) -> str:
    prioritized = []
    fallback = []
    for key, value in item.items():
        if isinstance(value, (dict, list)):
            continue
        normalized = str(value).strip()
        if not normalized:
            continue
        if any(hint in key.lower() for hint in TEXT_HINTS):
            prioritized.append(normalized)
        fallback.append(normalized)
    return "\n".join(prioritized or fallback)


def choose_title(item: dict[str, Any], index: int) -> str:
    for key, value in item.items():
        if any(hint in key.lower() for hint in TITLE_HINTS) and value:
            return str(value).strip()[:120]
    return f"Item {index}"


def parse_json(input_path: Path) -> list[dict]:
    payload = load_payload(input_path)
    records: list[dict] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            item = {"value": item}
        text = choose_text(item)
        if not text:
            continue
        records.append(
            build_record(
                source_file=str(input_path),
                record_id=f"item-{index}",
                title=choose_title(item, index),
                text=text,
                metadata={"source_type": "json", "raw": item},
            )
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse JSON or JSONL into normalized jsonl records.")
    parser.add_argument("input", type=Path, help="JSON or JSONL path")
    parser.add_argument("output", type=Path, help="Output jsonl path")
    args = parser.parse_args()

    records = parse_json(args.input)
    ensure_parent_dir(args.output)
    write_jsonl(args.output, records)
    print(f"Wrote {len(records)} record(s) to {args.output}")


if __name__ == "__main__":
    main()
