#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from common import build_record, ensure_parent_dir, write_jsonl


TEXT_HINTS = ("text", "comment", "review", "content", "body", "message", "feedback", "note", "description")
TITLE_HINTS = ("title", "subject", "heading", "name")


def choose_text(row: dict[str, str]) -> str:
    prioritized = [value for key, value in row.items() if any(hint in key.lower() for hint in TEXT_HINTS) and value]
    if prioritized:
        return "\n".join(prioritized)
    return "\n".join(value for value in row.values() if value)


def choose_title(row: dict[str, str], row_number: int) -> str:
    for key, value in row.items():
        if any(hint in key.lower() for hint in TITLE_HINTS) and value:
            return value[:120]
    return f"Row {row_number}"


def parse_csv(input_path: Path) -> list[dict]:
    records: list[dict] = []
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=2):
            normalized_row = {key: (value or "").strip() for key, value in row.items()}
            text = choose_text(normalized_row)
            if not text:
                continue
            records.append(
                build_record(
                    source_file=str(input_path),
                    record_id=f"row-{row_number}",
                    title=choose_title(normalized_row, row_number),
                    text=text,
                    metadata={
                        "source_type": "csv",
                        "row_number": row_number,
                        "column_map": normalized_row,
                    },
                )
            )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a CSV file into normalized jsonl records.")
    parser.add_argument("input", type=Path, help="CSV path")
    parser.add_argument("output", type=Path, help="Output jsonl path")
    args = parser.parse_args()

    records = parse_csv(args.input)
    ensure_parent_dir(args.output)
    write_jsonl(args.output, records)
    print(f"Wrote {len(records)} record(s) to {args.output}")


if __name__ == "__main__":
    main()
