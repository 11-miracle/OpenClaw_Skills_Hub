#!/usr/bin/env python3
"""Send emails through SMTP with optional attachments."""

from __future__ import annotations

import argparse
import mimetypes
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _getenv_any(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip() != "":
            return value
    return default


def _split_recipients(values: list[str] | None) -> list[str]:
    recipients: list[str] = []
    for value in values or []:
        for item in value.split(","):
            cleaned = item.strip()
            if cleaned:
                recipients.append(cleaned)
    return recipients


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send email via SMTP with optional attachments."
    )
    parser.add_argument(
        "--smtp-host",
        default=_getenv_any("SMTP_HOST", "OPENCLAW_SMTP_HOST", default="smtp.163.com"),
    )
    parser.add_argument(
        "--smtp-port",
        type=int,
        default=int(_getenv_any("SMTP_PORT", "OPENCLAW_SMTP_PORT", default="465")),
    )
    parser.add_argument(
        "--smtp-user",
        default=_getenv_any("SMTP_USER", "OPENCLAW_SMTP_USER"),
    )
    parser.add_argument(
        "--smtp-password",
        default=_getenv_any("SMTP_PASSWORD", "OPENCLAW_SMTP_PASSWORD"),
    )
    parser.add_argument(
        "--from-addr",
        default=_getenv_any("SMTP_FROM", "OPENCLAW_SMTP_FROM"),
    )
    parser.add_argument("--to", action="append", help="Recipient(s), comma-separated.")
    parser.add_argument("--cc", action="append", help="CC recipient(s), comma-separated.")
    parser.add_argument(
        "--bcc", action="append", help="BCC recipient(s), comma-separated."
    )
    parser.add_argument("--subject", required=True, help="Email subject.")
    parser.add_argument("--body", default="", help="Email body text.")
    parser.add_argument("--body-file", help="Read body from file (utf-8).")
    parser.add_argument("--html", action="store_true", help="Treat body as HTML.")
    parser.add_argument(
        "--attach", action="append", default=[], help="Attachment path. Repeatable."
    )
    parser.add_argument("--starttls", action="store_true", help="Enable STARTTLS.")
    parser.add_argument(
        "--no-ssl",
        action="store_true",
        help="Use plain SMTP instead of implicit SSL.",
    )
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def _load_body(args: argparse.Namespace) -> str:
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    return args.body


def _attach_files(msg: EmailMessage, attachment_paths: list[str]) -> None:
    for raw_path in attachment_paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Attachment not found: {path}")
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type:
            maintype, subtype = mime_type.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"
        msg.add_attachment(
            path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=path.name,
        )


def _print_summary(
    *,
    sender: str,
    to_list: list[str],
    cc_list: list[str],
    bcc_list: list[str],
    subject: str,
    attachments: list[str],
    dry_run: bool,
) -> None:
    mode = "DRY-RUN" if dry_run else "SEND"
    print(f"[{mode}] From: {sender}")
    print(f"[{mode}] To: {', '.join(to_list) if to_list else '-'}")
    print(f"[{mode}] Cc: {', '.join(cc_list) if cc_list else '-'}")
    print(f"[{mode}] Bcc: {', '.join(bcc_list) if bcc_list else '-'}")
    print(f"[{mode}] Subject: {subject}")
    print(f"[{mode}] Attachments: {len(attachments)}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    to_list = _split_recipients(args.to)
    cc_list = _split_recipients(args.cc)
    bcc_list = _split_recipients(args.bcc)
    all_recipients = to_list + cc_list + bcc_list

    if not all_recipients:
        parser.error("At least one recipient is required via --to/--cc/--bcc.")

    if not args.smtp_user:
        parser.error("SMTP user is required (--smtp-user or SMTP_USER).")

    if not args.smtp_password:
        parser.error("SMTP password is required (--smtp-password or SMTP_PASSWORD).")

    sender = args.from_addr or args.smtp_user
    body = _load_body(args)

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = args.subject

    if args.html:
        msg.set_content("HTML email. If this appears, your client does not render HTML.")
        msg.add_alternative(body, subtype="html")
    else:
        msg.set_content(body)

    _attach_files(msg, args.attach)

    _print_summary(
        sender=sender,
        to_list=to_list,
        cc_list=cc_list,
        bcc_list=bcc_list,
        subject=args.subject,
        attachments=args.attach,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return 0

    use_ssl = not args.no_ssl
    use_starttls = args.starttls or _truthy(
        _getenv_any("SMTP_STARTTLS", "OPENCLAW_SMTP_STARTTLS")
    )

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(
                args.smtp_host, args.smtp_port, timeout=args.timeout
            ) as smtp:
                if args.verbose:
                    smtp.set_debuglevel(1)
                smtp.login(args.smtp_user, args.smtp_password)
                smtp.send_message(msg, from_addr=sender, to_addrs=all_recipients)
        else:
            with smtplib.SMTP(args.smtp_host, args.smtp_port, timeout=args.timeout) as smtp:
                if args.verbose:
                    smtp.set_debuglevel(1)
                smtp.ehlo()
                if use_starttls:
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(args.smtp_user, args.smtp_password)
                smtp.send_message(msg, from_addr=sender, to_addrs=all_recipients)
    except Exception as exc:
        print(f"[ERROR] Failed to send email: {exc}", file=sys.stderr)
        return 1

    print("[OK] Email sent successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
