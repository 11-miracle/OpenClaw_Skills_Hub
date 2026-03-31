#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import build_record, ensure_parent_dir, write_jsonl


def parse_pdf(input_path: Path) -> list[dict]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit("Missing dependency: pypdf. Install it from scripts/requirements.txt.") from exc

    reader = PdfReader(str(input_path))
    records: list[dict] = []

    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        metadata = {"source_type": "pdf", "page": index}
        if not text:
            text = "[NO_TEXT_EXTRACTED]"
            metadata["note"] = "No text extracted. The PDF may be scanned and need OCR."
        records.append(
            build_record(
                source_file=str(input_path),
                record_id=f"page-{index}",
                title=f"Page {index}",
                text=text,
                metadata=metadata,
            )
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a text-based PDF into normalized jsonl records.")
    parser.add_argument("input", type=Path, help="PDF path")
    parser.add_argument("output", type=Path, help="Output jsonl path")
    args = parser.parse_args()

    records = parse_pdf(args.input)
    ensure_parent_dir(args.output)
    write_jsonl(args.output, records)
    print(f"Wrote {len(records)} record(s) to {args.output}")


if __name__ == "__main__":
    main()
