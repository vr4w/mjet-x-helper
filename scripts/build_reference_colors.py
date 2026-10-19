from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "reference_colors.json"

SOURCES = {
    "PANTONE": "https://www.werbemittel24.com/info/seite/10133/pantone.html",
    "HKS": "https://www.druckcenter.de/service/hks_farbtabelle",
}


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": "MJET-X Helper offline reference import"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def percent(value: str) -> int:
    number = int(round(float(value.replace(",", "."))))
    return max(0, min(100, number))


def pantone_number_and_variant(name: str) -> tuple[str, str]:
    normalized = re.sub(r"\s+", " ", name.replace("Pantone", "", 1)).strip()
    parts = normalized.split()
    number = ""
    variant = ""
    for part in parts:
        if re.search(r"\d", part) and not number:
            number = part
        elif len(part) <= 2 and part.isalpha():
            variant = part.upper()
    return number, variant


def parse_pantone(text: str) -> list[dict]:
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", text, flags=re.IGNORECASE | re.DOTALL)
    colors: list[dict] = []
    for row in rows:
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 3:
            continue
        name = clean_text(cells[1])
        cmyk = clean_text(cells[2])
        if not name:
            continue
        if not name.lower().startswith("pantone "):
            name = f"Pantone {name}"
        match = re.search(r"C:(\d+) M:(\d+) Y:(\d+) K:(\d+)", cmyk)
        if not match:
            continue
        number, variant = pantone_number_and_variant(name)
        display_name = name.replace("Pantone ", "", 1).strip()
        if number and not variant:
            variant = "C"
            display_name = f"{display_name} C"
        colors.append(
            {
                "system": "PANTONE",
                "name": display_name,
                "number": number,
                "variant": variant,
                "c": percent(match.group(1)),
                "m": percent(match.group(2)),
                "y": percent(match.group(3)),
                "k": percent(match.group(4)),
            }
        )
    return deduplicate(colors)


def parse_hks(text: str) -> list[dict]:
    plain = clean_text(text)
    pattern = re.compile(
        r"HKS\s+(?P<number>\d+)\s+K\s+"
        r"(?P<kc>\d+)%\s+(?P<km>\d+)%\s+(?P<ky>\d+)%\s+(?P<kk>\d+)%\s+"
        r"N\s+(?P<nc>\d+)%\s+(?P<nm>\d+)%\s+(?P<ny>\d+)%\s+(?P<nk>\d+)%",
        flags=re.IGNORECASE,
    )
    colors: list[dict] = []
    for match in pattern.finditer(plain):
        number = match.group("number")
        for variant, prefix in (("K", "k"), ("N", "n")):
            colors.append(
                {
                    "system": "HKS",
                    "name": f"HKS {number} {variant}",
                    "number": number,
                    "variant": variant,
                    "c": percent(match.group(f"{prefix}c")),
                    "m": percent(match.group(f"{prefix}m")),
                    "y": percent(match.group(f"{prefix}y")),
                    "k": percent(match.group(f"{prefix}k")),
                }
            )
    return deduplicate(colors)


def deduplicate(colors: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for color in colors:
        key = (
            str(color.get("system", "")).upper(),
            str(color.get("name", "")).casefold(),
            str(color.get("number", "")).casefold(),
            str(color.get("variant", "")).casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(color)
    return result


def main() -> None:
    pantone_html = fetch(SOURCES["PANTONE"])
    hks_html = fetch(SOURCES["HKS"])
    pantone = parse_pantone(pantone_html)
    hks = parse_hks(hks_html)
    payload = {
        "version": 1,
        "generated_by": "scripts/build_reference_colors.py",
        "sources": SOURCES,
        "note": (
            "Referenzwerte nur als Ausgangspunkt im Farbmischer. "
            "Keine MPRINT-Produktionsfreigabe und keine farbverbindliche Simulation."
        ),
        "colors": sorted(pantone + hks, key=lambda item: (item["system"], item["number"], item["variant"], item["name"])),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PANTONE: {len(pantone)}")
    print(f"HKS: {len(hks)}")
    print(f"Gesamt: {len(payload['colors'])}")
    print(f"Datei: {OUTPUT}")


if __name__ == "__main__":
    main()
