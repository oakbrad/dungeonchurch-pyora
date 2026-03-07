#!/usr/bin/env python3
"""Generate the 'Pyora Setting' section of README.md from homebrew JSON files."""

import json
import re
from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).parent.parent.parent

FIVE_TOOLS_BASE = "https://5e.dungeon.church"

CHECK = "\u2705"
WARN = "\u26a0\ufe0f"
CROSS = "\u274c"

# Standard 5etools item type abbreviations
ITEM_TYPE_MAP = {
    "M": "Melee Weapon",
    "R": "Ranged Weapon",
    "S": "Shield",
    "LA": "Light Armor",
    "MA": "Medium Armor",
    "HA": "Heavy Armor",
    "P": "Potion",
    "RG": "Ring",
    "RD": "Rod",
    "WD": "Wand",
    "SC": "Scroll",
    "G": "Gear",
    "FD": "Food/Drink",
    "$": "Currency",
    "$A": "Currency (Abstract)",
    "T": "Tool",
    "INS": "Instrument",
    "AT": "Artisan Tool",
    "EXP": "Explosive",
    "OTH": "Other",
    "GS": "Gaming Set",
    "TG": "Trade Good",
    "SCF": "Spellcasting Focus",
    "GV": "Generic Variant",
}

# Each category config: (json_key, file, heading, 5etools_page, has_art, has_token)
CATEGORY_CONFIGS = [
    ("book",            "zines", "Books",              "book.html",                True,  False),
    ("condition",       "main",  "Conditions",          "conditionsdiseases.html",  True,  False),
    ("language",        "main",  "Languages",           "languages.html",           False, False),
    ("race+subrace",    "main",  "Species (Races)",     "races.html",               False, False),
    ("deity",           "main",  "Deities",             "deities.html",             True,  False),
    ("item",            "main",  "Items",               "items.html",               True,  False),
    ("magicvariant",    "main",  "Magic Variants",      "items.html",               False, False),
    ("monster",         "main",  "Bestiary",            "bestiary.html",            True,  True),
    ("monster",         "npcs",  "NPCs",                "bestiary.html",            True,  True),
    ("hazard",          "main",  "Hazards",             "trapshazards.html",        False, False),
    ("optionalfeature", "main",  "Optional Features",   "optionalfeatures.html",    False, False),
    ("table",           "both",  "Tables",              "tables.html",              False, False),
    ("variantrule",     "main",  "House Rules",         "variantrules.html",        False, False),
]


def load_json(filename: str) -> dict:
    with open(REPO_ROOT / filename, encoding="utf-8") as f:
        return json.load(f)


def extract_wiki_link(entry: dict, key: str = "") -> str | None:
    """Extract a wiki link from a JSON entry.

    Search order:
    1. {@link ... in the wiki|URL} pattern anywhere in the entry
    2. 'Dungeon Church Lore' inset in fluff.entries or entries
    3. Any lore.dungeon.church link found anywhere
    """
    entry_str = json.dumps(entry)

    # 1. "in the wiki" pattern
    match = re.search(
        r'\{@link\s+[^|]+\s+in the wiki\|(https://lore\.dungeon\.church/[^}]+)\}',
        entry_str,
    )
    if match:
        return match.group(1)

    # 2. Dungeon Church Lore inset (check fluff.entries and top-level entries)
    for entries_list in [
        entry.get("fluff", {}).get("entries", []) if isinstance(entry.get("fluff"), dict) else [],
        entry.get("entries", []),
    ]:
        for e in entries_list:
            if isinstance(e, dict) and e.get("name") == "Dungeon Church Lore":
                inset_str = json.dumps(e)
                link = re.search(r'https://lore\.dungeon\.church/doc/[^"|}\\)\s]+', inset_str)
                if link:
                    return link.group()

    # 3. Any lore.dungeon.church/doc/ link
    match = re.search(r'https://lore\.dungeon\.church/doc/[^"|}\\)\s]+', entry_str)
    if match:
        return match.group()

    return None


def make_5etools_url(name: str, source: str, page: str) -> str:
    """Build a 5eTools URL for an entry."""
    anchor = f"{quote(name.lower())}_{source.lower()}"
    return f"{FIVE_TOOLS_BASE}/{page}#{anchor}"


def get_art_url(entry: dict, key: str) -> str | None:
    """Get the primary art URL for an entry."""
    if key == "deity":
        sym = entry.get("symbolImg", {})
        href = sym.get("href", {}) if isinstance(sym, dict) else {}
        return href.get("url")
    if key == "book":
        cover = entry.get("cover", {})
        return cover.get("url") if isinstance(cover, dict) else None
    fluff = entry.get("fluff", {})
    if isinstance(fluff, dict) and fluff.get("images"):
        href = fluff["images"][0].get("href", {})
        return href.get("url")
    return None


def get_token_url(entry: dict) -> str | None:
    """Get the token image URL for a monster/NPC."""
    token = entry.get("tokenHref")
    if isinstance(token, dict):
        return token.get("url")
    return None


def img_check(url: str) -> str:
    """Return CHECK for objectstorage-hosted images, WARN for others."""
    return CHECK if "objectstorage" in url else WARN


def get_sound_url(entry: dict) -> str | None:
    """Get the sound clip URL for an entry, if external."""
    clip = entry.get("soundClip")
    if isinstance(clip, dict) and clip.get("type") == "external":
        return clip.get("url")
    return None


def get_creature_type(entry: dict) -> str:
    """Extract creature type string from a monster/NPC entry."""
    t = entry.get("type", "")
    if isinstance(t, dict):
        return t.get("type", "").capitalize()
    return t.capitalize() if isinstance(t, str) else ""


def get_item_type(entry: dict, type_map: dict) -> str:
    """Look up the full item type name from the abbreviation."""
    abbr = entry.get("type")
    if not abbr:
        return ""
    # Magic variants have type like "GV|DMG" — use part before |
    abbr = abbr.split("|")[0]
    return type_map.get(abbr, abbr)


def build_books_section(books: list, zine_data: dict) -> str:
    """Render books as cover images with links instead of a table."""
    lines = ["## Books", ""]

    for book in sorted(books, key=lambda b: b["name"]):
        book_id = book.get("id", "").lower()
        url_5e = f"{FIVE_TOOLS_BASE}/book.html#{book_id}"
        cover = book.get("cover", {})
        cover_url = cover.get("url", "") if isinstance(cover, dict) else ""

        if cover_url:
            lines.append(f"[![{book['name']}]({cover_url})]({url_5e})")
        else:
            lines.append(f"[{book['name']}]({url_5e})")
        lines.append("")
        lines.append(f"**{book['name']}**")
        lines.append("")

    return "\n".join(lines)


def build_table(rows: list[dict], cols: list[str]) -> str:
    """Build a markdown table from rows using the given column specs.

    Each col name is also the key in the row dict.
    """
    lines = ["| " + " | ".join(cols) + " |"]
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")

    for row in rows:
        cells = [row.get(col, "") for col in cols]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def get_source(entry: dict, key: str) -> str:
    """Get the source for an entry, handling magicvariant special case."""
    if key == "magicvariant":
        return entry.get("inherits", {}).get("source", entry.get("source", ""))
    return entry.get("source", "")


def process_entries(entries: list, key: str, page: str, show_art: bool, show_token: bool, item_type_map: dict | None = None) -> list[dict]:
    """Process a list of entries into table rows."""
    rows = []
    for entry in sorted(entries, key=lambda e: e["name"]):
        name = entry["name"]
        source = get_source(entry, key)
        wiki = extract_wiki_link(entry, key)
        url_5e = make_5etools_url(name, source, page)

        row = {
            "Name": f"[{name}]({url_5e})",
            "Wiki": f"[{CHECK}]({wiki})" if wiki else CROSS,
        }

        # Category-specific extra columns
        if key in ("monster",):
            row["Type"] = get_creature_type(entry)
        if key in ("item", "magicvariant") and item_type_map:
            row["Type"] = get_item_type(entry, item_type_map)
        if key == "deity":
            domains = entry.get("domains", [])
            row["Domains"] = ", ".join(domains) if domains else ""

        if show_art:
            art_url = get_art_url(entry, key)
            row["Art"] = f"[{img_check(art_url)}]({art_url})" if art_url else CROSS
        if show_token:
            token_url = get_token_url(entry)
            row["Token"] = f'[<img src="{token_url}" width="25">]({token_url})' if token_url else CROSS
            if token_url and "objectstorage" not in token_url:
                row["Token"] = f'[{WARN}<img src="{token_url}" width="25">]({token_url})'

        # Sound column for monsters
        if key == "monster":
            sound_url = get_sound_url(entry)
            row["Sound"] = f"[{img_check(sound_url)}]({sound_url})" if sound_url else CROSS

        rows.append(row)
    return rows


def process_races(main_data: dict, page: str) -> list[dict]:
    """Process races and subraces into a combined table."""
    rows = []

    # Standalone races (those without subraces)
    race_names_with_subs = {sr["raceName"] for sr in main_data.get("subrace", [])}
    for race in main_data.get("race", []):
        if race["name"] in race_names_with_subs:
            continue
        wiki = extract_wiki_link(race)
        source = race.get("source", "")
        url_5e = make_5etools_url(race["name"], source, page)
        sound_url = get_sound_url(race)
        rows.append({
            "Name": f"[{race['name']}]({url_5e})",
            "Subrace": "",
            "Wiki": f"[{CHECK}]({wiki})" if wiki else CROSS,
            "Sound": f"[{img_check(sound_url)}]({sound_url})" if sound_url else CROSS,
        })

    # Subraces displayed as "SubraceName (RaceName)"
    for sr in main_data.get("subrace", []):
        display_name = f"{sr['name']} ({sr['raceName']})"
        wiki = extract_wiki_link(sr)
        source = sr.get("source", "")
        url_name = f"{sr['raceName']}, {sr['name']}"
        url_5e = make_5etools_url(url_name, source, page)
        sound_url = get_sound_url(sr)
        rows.append({
            "Name": f"[{display_name}]({url_5e})",
            "Subrace": CHECK,
            "Wiki": f"[{CHECK}]({wiki})" if wiki else CROSS,
            "Sound": f"[{img_check(sound_url)}]({sound_url})" if sound_url else CROSS,
        })

    rows.sort(key=lambda r: r["Name"])
    return rows


def process_tables(entries: list, page: str) -> list[dict]:
    """Process table entries — no wiki column, add dice column."""
    rows = []
    for entry in sorted(entries, key=lambda e: e["name"]):
        name = entry["name"]
        source = entry.get("source", "")
        url_5e = make_5etools_url(name, source, page)
        col_labels = entry.get("colLabels", [])
        dice = col_labels[0] if col_labels else ""

        rows.append({
            "Dice": dice,
            "Name": f"[{name}]({url_5e})",
        })
    return rows


def build_item_type_map(main_data: dict) -> dict:
    """Build item type lookup combining standard + custom itemType entries."""
    type_map = dict(ITEM_TYPE_MAP)
    for it in main_data.get("itemType", []):
        type_map[it["abbreviation"]] = it["name"]
    return type_map


def generate_setting_section(main_data: dict, npc_data: dict, zine_data: dict) -> str:
    """Generate the full '# Pyora Setting' section."""
    sections = ["# Pyora Setting"]
    item_type_map = build_item_type_map(main_data)

    for key, file_id, heading, page, show_art, show_token in CATEGORY_CONFIGS:
        # Special case: books rendered as images
        if key == "book":
            books = zine_data.get("book", [])
            if books:
                sections.append(build_books_section(books, zine_data))
            continue

        # Special case: races + subraces combined
        if key == "race+subrace":
            rows = process_races(main_data, page)
            if rows:
                sections.append(f"## {heading}")
                sections.append(build_table(rows, ["Name", "Subrace", "Wiki", "Sound"]))
            continue

        # Special case: tables from both files (no wiki, add dice)
        if key == "table" and file_id == "both":
            entries = list(main_data.get("table", []))
            entries.extend(npc_data.get("table", []))
            if entries:
                rows = process_tables(entries, page)
                sections.append(f"## {heading}")
                sections.append(build_table(rows, ["Dice", "Name"]))
            continue

        # Standard categories
        if file_id == "main":
            data = main_data
        elif file_id == "npcs":
            data = npc_data
        elif file_id == "zines":
            data = zine_data
        else:
            continue

        entries = data.get(key, [])
        if not entries:
            continue

        rows = process_entries(entries, key, page, show_art, show_token, item_type_map)

        # Build column list based on category
        cols = []
        if show_token:
            cols.append("Token")
        cols.append("Name")
        if key in ("monster",):
            cols.append("Type")
        if key in ("item", "magicvariant"):
            cols.append("Type")
        if key == "deity":
            cols.append("Domains")
        cols.append("Wiki")
        if show_art:
            cols.append("Art")
        if key == "monster":
            cols.append("Sound")

        sections.append(f"## {heading}")
        sections.append(build_table(rows, cols))

    return "\n\n".join(sections) + "\n"


def replace_section(readme_text: str, new_section: str) -> str:
    """Replace the '# Pyora Setting' section in README.md."""
    pattern = re.compile(r"^# Pyora Setting\s*$", re.MULTILINE)
    match = pattern.search(readme_text)
    if not match:
        raise ValueError("Could not find '# Pyora Setting' heading in README.md")

    start = match.start()

    next_heading = re.search(r"^# ", readme_text[match.end():], re.MULTILINE)
    if next_heading:
        end = match.end() + next_heading.start()
    else:
        end = len(readme_text)

    return readme_text[:start] + new_section + "\n" + readme_text[end:]


def main():
    main_data = load_json("Dungeon Church; Pyora.json")
    npc_data = load_json("Dungeon Church; Pyora NPCs.json")
    zine_data = load_json("Dungeon Church; Zines.json")

    new_section = generate_setting_section(main_data, npc_data, zine_data)

    readme_path = REPO_ROOT / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")
    updated = replace_section(readme_text, new_section)
    readme_path.write_text(updated, encoding="utf-8")

    print("README.md updated successfully.")


if __name__ == "__main__":
    main()
