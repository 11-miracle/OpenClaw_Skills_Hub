#!/usr/bin/env python3
"""Read emails from an IMAP mailbox with safe defaults."""

from __future__ import annotations

import argparse
import email
import imaplib
import json
import os
import shlex
import ssl
import sys
from datetime import datetime
from email.header import decode_header
from email.message import Message
from email.utils import getaddresses
from html import unescape
from re import sub
from typing import List


def getenv_any(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def getenv_int_any(*names: str, default: int) -> int:
    for name in names:
        raw = os.getenv(name, "").strip()
        if not raw:
            continue
        try:
            return int(raw)
        except ValueError:
            continue
    return default


def decode_payload(payload: bytes, charset: str | None) -> str:
    tried = set()
    for enc in (charset, "utf-8", "latin-1"):
        if not enc or enc in tried:
            continue
        tried.add(enc)
        try:
            return payload.decode(enc, errors="replace")
        except LookupError:
            continue
    return payload.decode("utf-8", errors="replace")


def decode_mime(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    chunks = []
    for item, enc in parts:
        if isinstance(item, bytes):
            try:
                chunks.append(item.decode(enc or "utf-8", errors="replace"))
            except LookupError:
                chunks.append(item.decode("utf-8", errors="replace"))
        else:
            chunks.append(item)
    return "".join(chunks).strip()


def clean_text(text: str) -> str:
    text = unescape(text)
    text = sub(r"\s+", " ", text)
    return text.strip()


def html_to_text(html: str) -> str:
    no_scripts = sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    no_tags = sub(r"(?is)<[^>]+>", " ", no_scripts)
    return clean_text(no_tags)


def extract_text(msg: Message, max_chars: int) -> str:
    plain_chunks: List[str] = []
    html_chunks: List[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            if ctype not in ("text/plain", "text/html"):
                continue
            if part.get_content_disposition() == "attachment":
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            text = decode_payload(payload, part.get_content_charset())
            if ctype == "text/plain":
                plain_chunks.append(clean_text(text))
            else:
                html_chunks.append(html_to_text(text))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            text = decode_payload(payload, msg.get_content_charset())
            ctype = (msg.get_content_type() or "").lower()
            if ctype == "text/html":
                html_chunks.append(html_to_text(text))
            else:
                plain_chunks.append(clean_text(text))

    text = " ".join(chunk for chunk in plain_chunks if chunk).strip()
    if not text:
        text = " ".join(chunk for chunk in html_chunks if chunk).strip()
    if max_chars > 0:
        text = text[:max_chars]
    return text


def parse_addresses(value: str | None) -> str:
    if not value:
        return ""
    pairs = getaddresses([value])
    rendered = []
    for name, addr in pairs:
        name_decoded = decode_mime(name)
        if name_decoded and addr:
            rendered.append(f"{name_decoded} <{addr}>")
        elif addr:
            rendered.append(addr)
        elif name_decoded:
            rendered.append(name_decoded)
    return ", ".join(rendered)


def parse_date(value: str | None) -> str:
    if not value:
        return ""
    return decode_mime(value)


def imap_date_str(value: str) -> str:
    dt = datetime.strptime(value, "%Y-%m-%d")
    return dt.strftime("%d-%b-%Y")


def build_criteria(args: argparse.Namespace) -> List[str]:
    criteria: List[str] = []

    if args.search:
        criteria.extend(shlex.split(args.search))
    else:
        criteria.append("ALL")

    if args.unseen:
        criteria.append("UNSEEN")
    if args.since:
        criteria.extend(["SINCE", imap_date_str(args.since)])
    if args.before:
        criteria.extend(["BEFORE", imap_date_str(args.before)])
    if args.sender:
        criteria.extend(["FROM", f'"{args.sender}"'])
    if args.subject:
        criteria.extend(["SUBJECT", f'"{args.subject}"'])

    return criteria


def fetch_message_bytes(data: List[object]) -> bytes:
    chunks: List[bytes] = []
    for item in data:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
            chunks.append(item[1])
    return b"".join(chunks)


def render_table(rows: List[dict]) -> str:
    if not rows:
        return "No emails matched the query."

    headers = ["idx", "uid", "date", "from", "subject"]
    widths = {h: len(h) for h in headers}

    def short(v: str, n: int) -> str:
        if len(v) <= n:
            return v
        if n <= 3:
            return v[:n]
        return v[: n - 3] + "..."

    normalized = []
    for row in rows:
        item = {
            "idx": str(row["idx"]),
            "uid": str(row["uid"]),
            "date": short(row.get("date", ""), 26),
            "from": short(row.get("from", ""), 34),
            "subject": short(row.get("subject", ""), 60),
        }
        normalized.append(item)
        for h in headers:
            widths[h] = max(widths[h], len(item[h]))

    line = " | ".join(h.ljust(widths[h]) for h in headers)
    sep = "-+-".join("-" * widths[h] for h in headers)
    body = [
        " | ".join(item[h].ljust(widths[h]) for h in headers) for item in normalized
    ]
    return "\n".join([line, sep] + body)


def connect_imap(host: str, port: int, insecure: bool, timeout: float) -> imaplib.IMAP4_SSL:
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        return imaplib.IMAP4_SSL(host=host, port=port, ssl_context=ctx, timeout=timeout)
    except TypeError:
        return imaplib.IMAP4_SSL(host=host, port=port, ssl_context=ctx)


def host_requires_id(host: str) -> bool:
    h = host.lower().strip()
    return h in {"imap.163.com", "imap.126.com", "imap.yeah.net"}


def imap_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def maybe_send_id(client: imaplib.IMAP4_SSL, args: argparse.Namespace) -> None:
    should_send = args.id_mode == "always" or (
        args.id_mode == "auto" and host_requires_id(args.host)
    )
    if not should_send:
        return

    # 163/126/yeah servers may require RFC2971 ID after LOGIN and before SELECT.
    imaplib.Commands["ID"] = ("AUTH", "SELECTED")
    payload = (
        f'("name" {imap_quote(args.id_name)} '
        f'"version" {imap_quote(args.id_version)} '
        f'"vendor" {imap_quote(args.id_vendor)})'
    )
    typ, data = client._simple_command("ID", payload)
    if typ != "OK":
        detail = ""
        if data and isinstance(data[0], bytes):
            detail = data[0].decode(errors="replace")
        raise RuntimeError(f"IMAP ID command rejected. {detail}".strip())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read emails from IMAP mailbox.")
    p.add_argument(
        "--host",
        default=getenv_any("IMAP_HOST", "OPENCLAW_IMAP_HOST"),
        help="IMAP hostname",
    )
    p.add_argument(
        "--port",
        type=int,
        default=getenv_int_any("IMAP_PORT", "OPENCLAW_IMAP_PORT", default=993),
        help="IMAP SSL port",
    )
    p.add_argument(
        "--username",
        default=getenv_any("IMAP_USERNAME", "OPENCLAW_IMAP_USERNAME"),
        help="IMAP username",
    )
    p.add_argument(
        "--password",
        default="",
        help="IMAP password (prefer env var instead of passing directly)",
    )
    p.add_argument(
        "--password-env",
        default="IMAP_PASSWORD",
        help="Environment variable containing IMAP password",
    )
    p.add_argument(
        "--mailbox",
        default=getenv_any("IMAP_MAILBOX", "OPENCLAW_IMAP_MAILBOX", default="INBOX"),
        help="Mailbox to select",
    )
    p.add_argument(
        "--search",
        default="ALL",
        help='Raw IMAP search clause, e.g. \'UNSEEN SINCE "01-Mar-2026"\'',
    )
    p.add_argument("--unseen", action="store_true", help="Append UNSEEN filter")
    p.add_argument("--since", default="", help="Filter from date (YYYY-MM-DD)")
    p.add_argument("--before", default="", help="Filter before date (YYYY-MM-DD)")
    p.add_argument("--from", dest="sender", default="", help="Filter sender contains text")
    p.add_argument("--subject", default="", help="Filter subject contains text")
    p.add_argument("--limit", type=int, default=20, help="Maximum emails to fetch")
    p.add_argument("--include-body", action="store_true", help="Include body preview text")
    p.add_argument("--max-body-chars", type=int, default=500, help="Preview length if body is included")
    p.add_argument("--output", choices=["json", "table"], default="json")
    p.add_argument("--read-write", action="store_true", help="Open mailbox in read-write mode")
    p.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    p.add_argument("--timeout", type=float, default=20.0, help="Network timeout seconds")
    p.add_argument(
        "--id-mode",
        choices=["auto", "always", "never"],
        default="auto",
        help="Send IMAP ID command after login. auto sends for 163/126/yeah hosts.",
    )
    p.add_argument("--id-name", default="imap-read-email", help="IMAP ID name field")
    p.add_argument("--id-version", default="1.0", help="IMAP ID version field")
    p.add_argument("--id-vendor", default="python", help="IMAP ID vendor field")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    password = (
        args.password
        or os.getenv(args.password_env, "")
        or getenv_any("IMAP_PASSWORD", "OPENCLAW_IMAP_PASSWORD")
    )
    if not args.host:
        parser.error(
            "Missing IMAP host. Set --host, IMAP_HOST, or OPENCLAW_IMAP_HOST."
        )
    if not args.username:
        parser.error(
            "Missing IMAP username. Set --username, IMAP_USERNAME, or OPENCLAW_IMAP_USERNAME."
        )
    if not password:
        parser.error(
            "Missing IMAP password. Set --password, "
            f"{args.password_env}, IMAP_PASSWORD, or OPENCLAW_IMAP_PASSWORD."
        )

    if args.since:
        imap_date_str(args.since)
    if args.before:
        imap_date_str(args.before)

    criteria = build_criteria(args)
    client = None

    try:
        client = connect_imap(args.host, args.port, args.insecure, args.timeout)
        client.login(args.username, password)
        maybe_send_id(client, args)
        typ, selected_data = client.select(args.mailbox, readonly=not args.read_write)
        if typ != "OK":
            detail = ""
            if selected_data and isinstance(selected_data[0], bytes):
                detail = selected_data[0].decode(errors="replace")
            raise RuntimeError(
                f"Cannot select mailbox: {args.mailbox}"
                + (f". Server said: {detail}" if detail else "")
            )

        typ, data = client.search(None, *criteria)
        if typ != "OK" or not data:
            raise RuntimeError("IMAP search failed.")

        ids = data[0].split()
        if not ids:
            rows: List[dict] = []
        else:
            if args.limit > 0:
                ids = ids[-args.limit :]
            ids = list(reversed(ids))

            rows = []
            for idx, mail_id in enumerate(ids, start=1):
                fetch_part = "(BODY.PEEK[HEADER] BODY.PEEK[TEXT])" if args.include_body else "(BODY.PEEK[HEADER])"
                typ, msg_data = client.fetch(mail_id, fetch_part)
                if typ != "OK":
                    continue

                raw = fetch_message_bytes(msg_data)
                if not raw:
                    continue

                msg = email.message_from_bytes(raw)
                row = {
                    "idx": idx,
                    "uid": mail_id.decode(errors="replace"),
                    "date": parse_date(msg.get("Date")),
                    "from": parse_addresses(msg.get("From")),
                    "to": parse_addresses(msg.get("To")),
                    "subject": decode_mime(msg.get("Subject")),
                }
                if args.include_body:
                    row["body_preview"] = extract_text(msg, args.max_body_chars)
                rows.append(row)

        if args.output == "json":
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            print(render_table(rows))
        return 0

    except imaplib.IMAP4.error as exc:
        print(f"IMAP error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
