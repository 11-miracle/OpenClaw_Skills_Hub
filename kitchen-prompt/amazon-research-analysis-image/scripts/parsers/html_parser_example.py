#!/usr/bin/env python3
from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path

from common import build_record, ensure_parent_dir, write_jsonl


class SimpleHTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if not cleaned:
            return
        if self.in_title:
            self.title_parts.append(cleaned)
        self.text_parts.append(cleaned)


def parse_html(input_path: Path) -> list[dict]:
    parser = SimpleHTMLTextExtractor()
    parser.feed(input_path.read_text(encoding="utf-8"))

    title = " ".join(parser.title_parts).strip() or input_path.stem
    text = "\n".join(parser.text_parts).strip()
    if not text:
        return []

    return [
        build_record(
            source_file=str(input_path),
            record_id="document-1",
            title=title[:120],
            text=text,
            metadata={"source_type": "html"},
        )
    ]


def main() -> None:
    cli = argparse.ArgumentParser(description="Parse an HTML file into normalized jsonl records.")
    cli.add_argument("input", type=Path, help="HTML path")
    cli.add_argument("output", type=Path, help="Output jsonl path")
    args = cli.parse_args()

    records = parse_html(args.input)
    ensure_parent_dir(args.output)
    write_jsonl(args.output, records)
    print(f"Wrote {len(records)} record(s) to {args.output}")


if __name__ == "__main__":
    main()
