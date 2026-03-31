#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class NormalizedRecord(TypedDict):
    source_file: str
    record_id: str
    title: str
    text: str
    metadata: dict[str, Any]


def build_record(
    *,
    source_file: str,
    record_id: str,
    title: str,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> NormalizedRecord:
    return {
        "source_file": source_file,
        "record_id": record_id,
        "title": title,
        "text": text,
        "metadata": metadata or {},
    }


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, records: list[NormalizedRecord]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
