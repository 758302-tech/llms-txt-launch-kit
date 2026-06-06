#!/usr/bin/env python3
"""Generate and validate llms.txt files without third-party dependencies."""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import textwrap
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[a-z0-9_\-]{12,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


@dataclass
class Entry:
    section: str
    title: str
    url: str
    description: str = ""
    source_path: Path | None = None


def slug_to_title(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    path = parsed.path if parsed.scheme else value
    name = Path(path.rstrip("/") or "home").name
    if name.lower() in {"index", "index.html", "readme.md", "readme.mdx"}:
        parent = Path(path).parent.name
        name = parent or "home"
    name = re.sub(r"\.(html?|mdx?|txt)$", "", name, flags=re.I)
    words = re.split(r"[-_]+", name)
    return " ".join(word.capitalize() for word in words if word) or "Home"


def normalize_url(url: str, base_url: str = "") -> str:
    url = url.strip()
    if url.startswith(("http://", "https://")):
        return url
    if base_url:
        return urllib.parse.urljoin(base_url.rstrip("/") + "/", url.lstrip("/"))
    return url


def read_url_list(path: Path, default_section: str, base_url: str) -> list[Entry]:
    entries: list[Entry] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if not parts[0]:
            raise ValueError(f"{path}:{line_number} has an empty URL")
        url = normalize_url(parts[0], base_url)
        title = parts[1] if len(parts) > 1 and parts[1] else slug_to_title(url)
        description = parts[2] if len(parts) > 2 else ""
        section = parts[3] if len(parts) > 3 and parts[3] else default_section
        entries.append(Entry(section=section, title=title, url=url, description=description))
    return entries


def strip_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip()
    metadata: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip().strip("\"'")
    return metadata, text[end + 4 :].lstrip()


def first_heading(text: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, flags=re.M)
    return match.group(1).strip() if match else ""


def first_paragraph(text: str) -> str:
    for block in re.split(r"\n\s*\n", text):
        clean = block.strip()
        if not clean or clean.startswith(("#", "```", "- ", "* ", ">")):
            continue
        clean = re.sub(r"\s+", " ", clean)
        return clean[:220]
    return ""


def local_doc_url(path: Path, root: Path, base_url: str) -> str:
    relative = path.relative_to(root).as_posix()
    if relative.lower() == "readme.md":
        relative = "index.md"
    return normalize_url(relative, base_url)


def read_markdown_dir(input_dir: Path, default_section: str, base_url: str) -> list[Entry]:
    entries: list[Entry] = []
    ignored = {".git", "node_modules", "dist", "build", ".next", ".cache"}
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".mdx"}:
            continue
        if any(part in ignored for part in path.parts):
            continue
        raw = path.read_text(encoding="utf-8")
        metadata, body = strip_frontmatter(raw)
        title = metadata.get("title") or first_heading(body) or slug_to_title(path.name)
        description = metadata.get("description") or first_paragraph(body)
        section = metadata.get("llms_section") or metadata.get("section") or default_section
        entries.append(
            Entry(
                section=section,
                title=title,
                url=local_doc_url(path, input_dir, base_url),
                description=description,
                source_path=path,
            )
        )
    return entries


def fetch_sitemap(sitemap_url: str, default_section: str) -> list[Entry]:
    with urllib.request.urlopen(sitemap_url, timeout=20) as response:
        data = response.read()
    root = ET.fromstring(data)
    entries: list[Entry] = []
    for loc in root.findall(".//{*}loc"):
        if not loc.text:
            continue
        url = loc.text.strip()
        entries.append(Entry(section=default_section, title=slug_to_title(url), url=url))
    return entries


def render_llms_txt(title: str, description: str, entries: list[Entry], notes: str = "") -> str:
    grouped: dict[str, list[Entry]] = {}
    for entry in entries:
        grouped.setdefault(entry.section, []).append(entry)

    lines = [f"# {title}", ""]
    if description:
        lines.extend([f"> {description}", ""])
    if notes:
        lines.extend([textwrap.dedent(notes).strip(), ""])

    for section, section_entries in grouped.items():
        lines.extend([f"## {section}", ""])
        for entry in section_entries:
            item = f"- [{entry.title}]({entry.url})"
            if entry.description:
                item += f": {entry.description}"
            lines.append(item)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_llms_full(title: str, description: str, entries: list[Entry], max_chars: int) -> str:
    lines = [f"# {title}", ""]
    if description:
        lines.extend([f"> {description}", ""])
    lines.extend(["This file combines local Markdown source content for LLM context.", ""])

    for entry in entries:
        if not entry.source_path:
            continue
        raw = entry.source_path.read_text(encoding="utf-8")
        _, body = strip_frontmatter(raw)
        body = body.strip()
        if max_chars > 0 and len(body) > max_chars:
            body = body[:max_chars].rstrip() + "\n\n[Truncated]"
        lines.extend([f"## {entry.title}", "", f"Source: {entry.url}", "", body, ""])
    return "\n".join(lines).rstrip() + "\n"


def collect_entries(args: argparse.Namespace) -> list[Entry]:
    entries: list[Entry] = []
    if args.url_list:
        entries.extend(read_url_list(Path(args.url_list), args.section, args.base_url))
    if args.input_dir:
        entries.extend(read_markdown_dir(Path(args.input_dir), args.section, args.base_url))
    if args.sitemap:
        entries.extend(fetch_sitemap(args.sitemap, args.section))
    if not entries:
        raise ValueError("provide --url-list, --input-dir, or --sitemap")
    return entries


def command_generate(args: argparse.Namespace) -> int:
    entries = collect_entries(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    llms_txt = render_llms_txt(args.title, args.description, entries, args.notes)
    (output_dir / "llms.txt").write_text(llms_txt, encoding="utf-8")

    if args.full:
        full_txt = render_llms_full(args.title, args.description, entries, args.max_full_chars)
        (output_dir / "llms-full.txt").write_text(full_txt, encoding="utf-8")

    print(f"wrote {output_dir / 'llms.txt'}")
    if args.full:
        print(f"wrote {output_dir / 'llms-full.txt'}")
    return 0


def validate_text(text: str) -> list[str]:
    warnings: list[str] = []
    lines = text.splitlines()
    nonempty = [(index + 1, line) for index, line in enumerate(lines) if line.strip()]

    if not nonempty or not nonempty[0][1].startswith("# "):
        warnings.append("missing required H1 as the first non-empty line")

    h1_count = sum(1 for line in lines if line.startswith("# "))
    if h1_count != 1:
        warnings.append(f"expected exactly one H1, found {h1_count}")

    if not any(line.startswith("> ") for line in lines[:8]):
        warnings.append("recommended blockquote summary not found near the top")

    section = ""
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("## "):
            section = stripped[3:].strip()
        if stripped.startswith("- "):
            if not section:
                warnings.append(f"line {index}: list item appears before an H2 section")
            if not re.search(r"\[[^\]]+\]\([^)]+\)", stripped):
                warnings.append(f"line {index}: list item is missing a markdown link")
            if "):" not in stripped and ") " not in stripped:
                warnings.append(f"line {index}: add a short description after the link")

    if re.search(r"\b(TODO|YOUR_|example\.com|replace me)\b", text, flags=re.I):
        warnings.append("placeholder text is still present")

    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            warnings.append("possible secret or credential pattern detected")
            break

    return warnings


def command_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    text = path.read_text(encoding="utf-8")
    warnings = validate_text(text)
    if warnings:
        print(f"{path}: {len(warnings)} issue(s)")
        for warning in warnings:
            print(f"- {html.escape(warning)}")
        return 1
    print(f"{path}: ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and validate llms.txt files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="generate llms.txt from URL lists, local Markdown, or a sitemap")
    generate.add_argument("--title", required=True, help="site or product title")
    generate.add_argument("--description", default="", help="short blockquote summary")
    generate.add_argument("--base-url", default="", help="base URL for relative local paths")
    generate.add_argument("--section", default="Docs", help="default H2 section name")
    generate.add_argument("--url-list", help="pipe-delimited URL list: url | title | description | section")
    generate.add_argument("--input-dir", help="local Markdown or MDX directory")
    generate.add_argument("--sitemap", help="sitemap.xml URL")
    generate.add_argument("--output-dir", default=".", help="where to write llms.txt")
    generate.add_argument("--notes", default="", help="optional body text below the summary")
    generate.add_argument("--full", action="store_true", help="also write llms-full.txt from local Markdown content")
    generate.add_argument("--max-full-chars", type=int, default=12000, help="max characters per local source in llms-full.txt")
    generate.set_defaults(func=command_generate)

    validate = subparsers.add_parser("validate", help="validate a generated llms.txt file")
    validate.add_argument("path", help="path to llms.txt")
    validate.set_defaults(func=command_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
