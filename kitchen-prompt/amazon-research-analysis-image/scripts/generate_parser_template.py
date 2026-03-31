#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


TEMPLATES = {
    "excel": """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_record(*, source_file: str, record_id: str, title: str, text: str, metadata: dict | None = None) -> dict:
    return {
        "source_file": source_file,
        "record_id": record_id,
        "title": title,
        "text": text,
        "metadata": metadata or {},
    }


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\\n")


def parse_file(input_path: Path) -> list[dict]:
    # TODO: replace this stub with workbook parsing logic.
    return [
        build_record(
            source_file=str(input_path),
            record_id="sheet1-row1",
            title="Row 1",
            text="Replace with extracted Excel row text.",
            metadata={"source_type": "excel"},
        )
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse an Excel-like source into normalized jsonl.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    records = parse_file(args.input)
    ensure_parent_dir(args.output)
    write_jsonl(args.output, records)


if __name__ == "__main__":
    main()
""",
    "pdf": """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_record(*, source_file: str, record_id: str, title: str, text: str, metadata: dict | None = None) -> dict:
    return {
        "source_file": source_file,
        "record_id": record_id,
        "title": title,
        "text": text,
        "metadata": metadata or {},
    }


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\\n")


def parse_file(input_path: Path) -> list[dict]:
    # TODO: replace this stub with PDF extraction logic.
    return [
        build_record(
            source_file=str(input_path),
            record_id="page-1",
            title="Page 1",
            text="Replace with extracted PDF text.",
            metadata={"source_type": "pdf", "page": 1},
        )
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a PDF source into normalized jsonl.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    records = parse_file(args.input)
    ensure_parent_dir(args.output)
    write_jsonl(args.output, records)


if __name__ == "__main__":
    main()
""",
    "csv": """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_record(*, source_file: str, record_id: str, title: str, text: str, metadata: dict | None = None) -> dict:
    return {
        "source_file": source_file,
        "record_id": record_id,
        "title": title,
        "text": text,
        "metadata": metadata or {},
    }


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\\n")


def parse_file(input_path: Path) -> list[dict]:
    # TODO: replace this stub with CSV parsing logic.
    return [
        build_record(
            source_file=str(input_path),
            record_id="row-1",
            title="Row 1",
            text="Replace with extracted CSV row text.",
            metadata={"source_type": "csv", "row_number": 1},
        )
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a CSV-like source into normalized jsonl.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    records = parse_file(args.input)
    ensure_parent_dir(args.output)
    write_jsonl(args.output, records)


if __name__ == "__main__":
    main()
""",
    "json": """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_record(*, source_file: str, record_id: str, title: str, text: str, metadata: dict | None = None) -> dict:
    return {
        "source_file": source_file,
        "record_id": record_id,
        "title": title,
        "text": text,
        "metadata": metadata or {},
    }


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\\n")


def parse_file(input_path: Path) -> list[dict]:
    # TODO: replace this stub with JSON parsing logic.
    return [
        build_record(
            source_file=str(input_path),
            record_id="item-1",
            title="Item 1",
            text="Replace with extracted JSON text.",
            metadata={"source_type": "json"},
        )
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a JSON-like source into normalized jsonl.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    records = parse_file(args.input)
    ensure_parent_dir(args.output)
    write_jsonl(args.output, records)


if __name__ == "__main__":
    main()
""",
    "text": """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_record(*, source_file: str, record_id: str, title: str, text: str, metadata: dict | None = None) -> dict:
    return {
        "source_file": source_file,
        "record_id": record_id,
        "title": title,
        "text": text,
        "metadata": metadata or {},
    }


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\\n")


def parse_file(input_path: Path) -> list[dict]:
    # TODO: replace this stub with TXT or Markdown parsing logic.
    return [
        build_record(
            source_file=str(input_path),
            record_id="chunk-1",
            title=input_path.stem,
            text="Replace with extracted text content.",
            metadata={"source_type": "text", "chunk_index": 1},
        )
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a text-like source into normalized jsonl.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    records = parse_file(args.input)
    ensure_parent_dir(args.output)
    write_jsonl(args.output, records)


if __name__ == "__main__":
    main()
""",
    "html": """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_record(*, source_file: str, record_id: str, title: str, text: str, metadata: dict | None = None) -> dict:
    return {
        "source_file": source_file,
        "record_id": record_id,
        "title": title,
        "text": text,
        "metadata": metadata or {},
    }


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\\n")


def parse_file(input_path: Path) -> list[dict]:
    # TODO: replace this stub with HTML text extraction logic.
    return [
        build_record(
            source_file=str(input_path),
            record_id="document-1",
            title=input_path.stem,
            text="Replace with extracted HTML text.",
            metadata={"source_type": "html"},
        )
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse an HTML-like source into normalized jsonl.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    records = parse_file(args.input)
    ensure_parent_dir(args.output)
    write_jsonl(args.output, records)


if __name__ == "__main__":
    main()
""",
}


def build_output_path(source_type: str, output: Path | None) -> Path:
    if output is not None:
        return output
    return Path.cwd() / f"{source_type}_parser_generated.py"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a parser scaffold for a specific source type.")
    parser.add_argument(
        "--source-type",
        choices=sorted(TEMPLATES.keys()),
        required=True,
        help="Source type to scaffold.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Where to write the generated parser file. Defaults to the current directory.",
    )
    args = parser.parse_args()

    output_path = build_output_path(args.source_type, args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(TEMPLATES[args.source_type], encoding="utf-8")
    print(f"Generated parser template: {output_path}")


if __name__ == "__main__":
    main()
