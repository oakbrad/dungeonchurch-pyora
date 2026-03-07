#!/usr/bin/env python3
"""Migrate asset URLs from various hosts to OCI Object Storage.

Finds {"type": "external", "url": "..."} objects in 5etools homebrew JSON
where the URL is not already on OCI, checks if the file exists on OCI,
and replaces the URL if so.
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError

REPO_ROOT = Path(__file__).parent.parent.parent
OCI_BASE = "https://objectstorage.us-sanjose-1.oraclecloud.com/n/axhus520kaxe/b/dungeonchurch-content/o/5e/"
REPO_STATIC_PREFIX = "oakbrad/dungeonchurch-pyora/main/static/"


def find_external_urls(obj):
    """Recursively yield URL strings from {"type": "external", "url": "..."} objects."""
    if isinstance(obj, dict):
        if obj.get("type") == "external" and "url" in obj:
            yield obj["url"]
        for v in obj.values():
            yield from find_external_urls(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from find_external_urls(item)


def build_candidates(url: str) -> list[str]:
    """Return candidate OCI URLs to try, based on filename and path conventions."""
    parsed = urlparse(url)
    # Decode percent-encoded characters (e.g. %20 -> space)
    path = unquote(parsed.path)
    filename = Path(path).name

    candidates = []
    # URL-encode the filename for use in OCI URLs (spaces -> %20, etc.)
    safe_filename = quote(filename)

    # For GitHub raw URLs from this repo, try the exact subpath after static/
    if REPO_STATIC_PREFIX in url:
        after_static = quote(unquote(url.split(REPO_STATIC_PREFIX, 1)[1]))
        candidates.append(OCI_BASE + after_static)

    # Convention-based candidates from the filename
    if filename.endswith(".mp3"):
        candidates.append(OCI_BASE + "sounds/" + safe_filename)
    elif "-token." in filename:
        candidates.append(OCI_BASE + "tokens/" + safe_filename)
    elif filename.startswith("tarot-"):
        candidates.append(OCI_BASE + "tarot/" + safe_filename)

    # Always try root as a fallback
    candidates.append(OCI_BASE + safe_filename)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def check_url(url: str) -> bool:
    """Send an HTTP HEAD request; return True if status 200."""
    try:
        req = Request(url, method="HEAD")
        resp = urlopen(req, timeout=10)
        return resp.status == 200
    except (URLError, OSError):
        return False


def main():
    parser = argparse.ArgumentParser(description="Migrate asset URLs to OCI Object Storage")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying files")
    args = parser.parse_args()

    json_files = sorted(REPO_ROOT.glob("Dungeon Church*.json"))
    if not json_files:
        print("No 'Dungeon Church*.json' files found.")
        sys.exit(1)

    total_migrated = 0
    total_not_found = 0

    for json_path in json_files:
        text = json_path.read_text(encoding="utf-8")
        data = json.loads(text)

        # Collect unique non-OCI external URLs
        urls = list(dict.fromkeys(
            u for u in find_external_urls(data) if "objectstorage" not in u
        ))

        if not urls:
            continue

        print(f"\n--- {json_path.name} ---")
        replacements = {}

        for url in urls:
            candidates = build_candidates(url)
            found = False
            for candidate in candidates:
                if check_url(candidate):
                    replacements[url] = candidate
                    print(f"  MIGRATED: {url}")
                    print(f"        -> {candidate}")
                    found = True
                    break
            if not found:
                print(f"  NOT FOUND: {url}")
                print(f"        checked {len(candidates)} candidate(s)")
                total_not_found += 1

        if replacements:
            total_migrated += len(replacements)
            if not args.dry_run:
                for old, new in replacements.items():
                    text = text.replace(old, new)
                json_path.write_text(text, encoding="utf-8")

    print(f"\n{total_migrated} migrated, {total_not_found} not found", end="")
    if args.dry_run and total_migrated:
        print(" (dry run — no files modified)")
    else:
        print()


if __name__ == "__main__":
    main()
