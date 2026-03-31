#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import build_record, ensure_parent_dir, write_jsonl


def split_chunks(content: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\n\s*\n+", content) if part.strip()]
    return parts or [content.strip()]


def parse_text(input_path: Path, chunked: bool) -> list[dict]:
    content = input_path.read_text(encoding="utf-8").strip()
    if not content:
        return []

    chunks = split_chunks(content) if chunked else [content]
    records: list[dict] = []
    for index, chunk in enumerate(chunks, start=1):
        records.append(
            build_record(
                source_file=str(input_path),
                record_id=f"chunk-{index}",
                title=input_path.stem if index == 1 else f"{input_path.stem} chunk {index}",
                text=chunk,
                metadata={"source_type": "text", "chunk_index": index},
            )
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse TXT or Markdown files into normalized jsonl records.")
    parser.add_argument("input", type=Path, help="TXT or Markdown path")
    parser.add_argument("output", type=Path, help="Output jsonl path")
    parser.add_argument("--chunked", action="store_true", help="Split content by blank lines into multiple records.")
    args = parser.parse_args()

    records = parse_text(args.input, args.chunked)
    ensure_parent_dir(args.output)
    write_jsonl(args.output, records)
    print(f"Wrote {len(records)} record(s) to {args.output}")


if __name__ == "__main__":
    main()
