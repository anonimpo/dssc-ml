#!/usr/bin/env python3
"""Extract DSSC photovoltaic properties from scraped DOAJ text snippets."""

import csv
import html
import re
import subprocess
from pathlib import Path


INPUT = Path("database_2018_13516220/doaj_2020_2026/scraped/green_dssc_materials_experimental_candidates_2020_2026.csv")
OUTPUT = Path("database_2018_13516220/doaj_2020_2026/scraped/green_dssc_properties_2020_2026.csv")


def clean_text(value):
    value = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def raw_text(path):
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    try:
        if p.suffix.lower() == ".pdf" or p.read_bytes()[:4] == b"%PDF":
            result = subprocess.run(
                ["pdftotext", str(p), "-"],
                check=True,
                text=True,
                capture_output=True,
                timeout=60,
            )
            return clean_text(result.stdout)
        return clean_text(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return ""


def first_match(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1), match.group(2) if len(match.groups()) > 1 else ""
    return "", ""


def all_pce(text):
    values = []
    patterns = [
        r"(?:PCE|power conversion efficiency|efficiency|η)\D{0,45}(\d+(?:\.\d+)?)\s*%",
        r"(\d+(?:\.\d+)?)\s*%\D{0,35}(?:PCE|power conversion efficiency|efficiency)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            try:
                value = float(match.group(1))
            except ValueError:
                continue
            if 0 < value <= 50:
                values.append(value)
    return values


def property_context(text):
    prop = re.compile(r"Voc|V_oc|open-circuit voltage|Jsc|J_sc|short-circuit current|fill factor|FF|PCE|power conversion efficiency|efficiency|η", re.I)
    snippets = []
    for match in prop.finditer(text):
        start = max(0, match.start() - 130)
        end = min(len(text), match.end() + 170)
        snippet = clean_text(text[start:end])
        if snippet and snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) >= 4:
            break
    return " | ".join(snippets)


def main():
    rows = list(csv.DictReader(INPUT.open(encoding="utf-8")))
    out = []
    text_cache = {}
    seen = set()

    for row in rows:
        key = (row["doi"], row["material"].lower(), row["role"])
        if key in seen:
            continue
        seen.add(key)

        path = row.get("local_file", "")
        if path not in text_cache:
            text_cache[path] = raw_text(path)
        text = clean_text(" ".join([row.get("performance_snippets", ""), text_cache[path]]))

        voc, voc_units = first_match(
            [
                r"(?:Voc|V_oc|open-circuit voltage)\D{0,35}(\d+(?:\.\d+)?)\s*(mV|V)",
                r"(\d+(?:\.\d+)?)\s*(mV|V)\D{0,35}(?:Voc|V_oc|open-circuit voltage)",
            ],
            text,
        )
        jsc, jsc_units = first_match(
            [
                r"(?:Jsc|J_sc|short-circuit current density|current density)\D{0,45}(\d+(?:\.\d+)?)\s*(mA\s*/?\s*cm(?:-2|\^?-?2|²)|mA\s*cm(?:-2|\^?-?2|²))",
                r"(\d+(?:\.\d+)?)\s*(mA\s*/?\s*cm(?:-2|\^?-?2|²)|mA\s*cm(?:-2|\^?-?2|²))\D{0,45}(?:Jsc|J_sc|short-circuit current density|current density)",
            ],
            text,
        )
        ff, ff_units = first_match(
            [
                r"(?:fill factor|FF)\D{0,35}(\d+(?:\.\d+)?)\s*(%)?",
            ],
            text,
        )

        pces = all_pce(text)
        pce = row.get("max_pce_percent_text_mined", "")
        if not pce and pces:
            pce = str(max(pces))

        out.append(
            {
                "year": row["year"],
                "material": row["material"],
                "role": row["role"],
                "voc": voc,
                "voc_units": voc_units,
                "jsc": jsc,
                "jsc_units": jsc_units,
                "ff": ff,
                "ff_units": ff_units,
                "pce_percent": pce,
                "paper_title": row["paper_title"],
                "doi": row["doi"],
                "journal": row["journal"],
                "source_url": row["source_url"],
                "local_file": row["local_file"],
                "property_context": property_context(text) or row.get("performance_snippets", ""),
            }
        )

    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "year",
            "material",
            "role",
            "voc",
            "voc_units",
            "jsc",
            "jsc_units",
            "ff",
            "ff_units",
            "pce_percent",
            "paper_title",
            "doi",
            "journal",
            "source_url",
            "local_file",
            "property_context",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)

    print(f"rows={len(out)}")
    print(f"output={OUTPUT}")
    print(f"with_voc={sum(bool(r['voc']) for r in out)}")
    print(f"with_jsc={sum(bool(r['jsc']) for r in out)}")
    print(f"with_ff={sum(bool(r['ff']) for r in out)}")
    print(f"with_pce={sum(bool(r['pce_percent']) for r in out)}")


if __name__ == "__main__":
    main()
