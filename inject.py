#!/usr/bin/env python3
"""
inject.py — Expand shortened social media URLs and write posts.csv.

Short links like http://vt.tiktok.com/ZS93M2uyo/ or https://fb.watch/abc/
are followed through HTTP redirects to their canonical full URLs so that
the embed renderer in index.html can extract the video/post ID correctly.

Usage:
    python inject.py urls.csv
    python inject.py urls.csv --output posts.csv   # default output
    python inject.py urls.csv --no-expand           # skip expansion

Requires: pip install requests
"""

import csv
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed — run:  pip install requests")


# ── Platform detection ────────────────────────────────────────────────────────

PLATFORM_PATTERNS: list[tuple[str, str]] = [
    (r"instagram\.com",                    "instagram"),
    (r"tiktok\.com",                       "tiktok"),
    (r"facebook\.com|fb\.com|fb\.watch",   "facebook"),
]

# URLs already in a fully embeddable form — skip expansion for these
FULL_URL_PATTERNS = [
    r"instagram\.com/(p|reel|tv)/[A-Za-z0-9_-]+",
    r"tiktok\.com/@[^/]+/video/\d+",
    r"facebook\.com/[^/]+/posts/\d+",
    r"facebook\.com/watch",
    r"facebook\.com/photo",
    r"facebook\.com/permalink",
]


def detect_platform(url: str) -> str:
    for pattern, name in PLATFORM_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return name
    return "unknown"


def is_full_url(url: str) -> bool:
    return any(re.search(p, url, re.IGNORECASE) for p in FULL_URL_PATTERNS)


# ── URL expansion ─────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def expand_url(url: str, session: requests.Session) -> str:
    try:
        r = session.get(url, allow_redirects=True, timeout=15, stream=True)
        r.close()
        return r.url
    except Exception as exc:
        print(f"  Warning: could not expand {url!r}: {exc}", file=sys.stderr)
        return url


# ── CSV loading ───────────────────────────────────────────────────────────────

def load_urls(path: Path) -> list[str]:
    urls: list[str] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        url_col = next((c for c in fieldnames if c.strip().lower() == "url"), None)
        if url_col:
            for row in reader:
                u = (row.get(url_col) or "").strip()
                if u:
                    urls.append(u)
        else:
            # No recognised header — treat first column as URLs, skip header row
            f.seek(0)
            plain = csv.reader(f)
            next(plain, None)
            for row in plain:
                if row and row[0].strip():
                    urls.append(row[0].strip())
    return urls


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    csv_path = Path(args[0])
    output_path = Path("posts.csv")
    do_expand = "--no-expand" not in args

    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            output_path = Path(args[idx + 1])
        else:
            sys.exit("Error: --output requires a file path")

    if not csv_path.exists():
        sys.exit(f"Error: '{csv_path}' not found")

    urls = load_urls(csv_path)
    total = len(urls)
    print(f"Loaded {total} URL{'s' if total != 1 else ''} from {csv_path}")

    result: list[str] = []
    with requests.Session() as session:
        session.headers.update(HEADERS)
        for i, url in enumerate(urls, 1):
            if do_expand and not is_full_url(url):
                print(f"  [{i}/{total}] Expanding  {url}")
                expanded = expand_url(url, session)
                if expanded != url:
                    print(f"           → {expanded}")
                result.append(expanded)
            else:
                result.append(url)

    output_path.write_text(
        "url\n" + "\n".join(result) + "\n",
        encoding="utf-8",
    )

    platform_counts: dict[str, int] = {}
    for url in result:
        p = detect_platform(url)
        platform_counts[p] = platform_counts.get(p, 0) + 1

    print(f"\nWrote {len(result)} URL{'s' if len(result) != 1 else ''} to {output_path}")
    for platform in ("instagram", "tiktok", "facebook", "unknown"):
        count = platform_counts.get(platform, 0)
        if count:
            print(f"  {platform:<12} {count}")


if __name__ == "__main__":
    main()
