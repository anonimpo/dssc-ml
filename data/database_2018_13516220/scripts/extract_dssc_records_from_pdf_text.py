#!/usr/bin/env python3
"""Extract high-confidence DSSC records from PDF/HTML text contexts.

This script targets clauses/sentences where Jsc, Voc, FF and PCE/eta are all
reported together. These are not as good as table extraction, but are higher
confidence than broad document-level text mining.
"""

import csv
import html
import re
import subprocess
from pathlib import Path

from bs4 import BeautifulSoup


RAW_DIR = Path("database_2018_13516220/doaj_2020_2026/scraped/raw")
FULL_FIELDS = Path("database_2018_13516220/doaj_2020_2026/scraped/green_dssc_full_fields_2020_2026.csv")
OUTPUT = Path("database_2018_13516220/doaj_2020_2026/scraped/green_dssc_text_records_with_core_properties_2020_2026.csv")


NUM = r"(\d+(?:\.\d+)?)"
JSC_UNIT = r"(mA\s*/?\s*cm(?:-2|\^?-?2|²)|mA\s*cm(?:-2|\^?-?2|²)|µA\s*/?\s*cm(?:-2|\^?-?2|²)|µA\s*cm(?:-2|\^?-?2|²))"

PATTERNS = [
    re.compile(
        rf"(?P<label>(?:for|of|with|using)\s+[^.;]{{2,120}}?)?\b(?:Jsc|JSC|J_sc|short[- ]circuit current density)\s*"
        rf"(?P<jsc>{NUM})\s*(?P<jsc_units>{JSC_UNIT})\D{{0,80}}"
        rf"(?:Voc|VOC|V_oc|open[- ]circuit voltage)\s*(?P<voc>{NUM})\s*(?P<voc_units>mV|V)\D{{0,80}}"
        rf"(?:FF|fill factor)\s*(?P<ff>{NUM})\D{{0,80}}"
        rf"(?:η|eta|PCE|efficiency)\s*(?:of\s*)?(?P<pce>{NUM})\s*%",
        re.I,
    ),
    re.compile(
        rf"(?P<label>(?:for|of|with|using)\s+[^.;]{{2,120}}?)?\b(?:Voc|VOC|V_oc|open[- ]circuit voltage)\s*(?P<voc>{NUM})\s*(?P<voc_units>mV|V)\D{{0,80}}"
        rf"(?:Jsc|JSC|J_sc|short[- ]circuit current density|current density)\s*(?P<jsc>{NUM})\s*(?P<jsc_units>{JSC_UNIT})\D{{0,80}}"
        rf"(?:FF|fill factor)\s*(?:of\s*)?(?P<ff>{NUM})\D{{0,80}}"
        rf"(?:η|eta|PCE|efficiency)\s*(?:of\s*)?(?P<pce>{NUM})\s*%",
        re.I,
    ),
]


def clean(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def read_text(path):
    p = Path(path)
    try:
        if p.suffix.lower() == ".pdf":
            result = subprocess.run(["pdftotext", "-layout", str(p), "-"], check=True, text=True, capture_output=True, timeout=60)
            return clean(result.stdout)
        soup = BeautifulSoup(p.read_text(encoding="utf-8", errors="ignore"), "lxml")
        return clean(soup.get_text(" ", strip=True))
    except Exception:
        return ""


def meta_by_doi_and_path():
    by_path = {}
    if FULL_FIELDS.exists():
        with FULL_FIELDS.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                path = row.get("local_file", "")
                if path and path not in by_path:
                    by_path[path] = row
    return by_path


def infer_doi(path):
    stem = path.stem
    return stem.replace("_", "/").replace("10/", "10.", 1) if stem.startswith("10_") else ""


def normalize_label(label):
    label = clean(label)
    label = re.sub(r"^(for|of|with|using)\s+", "", label, flags=re.I)
    label = re.sub(r"\b(the highest performance|highest performance|the DSSC|DSSC|was|were)$", "", label, flags=re.I)
    return clean(label.strip(" ,:;-"))


def context(text, start, end):
    return clean(text[max(0, start - 140) : min(len(text), end + 180)])


def main():
    meta_by_path = meta_by_doi_and_path()
    rows = []
    seen = set()
    for path in list(RAW_DIR.glob("*.pdf")) + list(RAW_DIR.glob("*.html")):
        text = read_text(path)
        if not text:
            continue
        meta = meta_by_path.get(str(path), {})
        if not meta:
            # Pair a downloaded PDF with its HTML metadata row.
            html_path = str(path.with_suffix(".html"))
            meta = meta_by_path.get(html_path, {})
        for pattern in PATTERNS:
            for match in pattern.finditer(text):
                try:
                    pce = float(match.group("pce"))
                except ValueError:
                    continue
                if not (0 < pce <= 50):
                    continue
                label = normalize_label(match.groupdict().get("label") or "")
                key = (meta.get("doi", str(path)), match.group("voc"), match.group("jsc"), match.group("ff"), match.group("pce"), label)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "year": meta.get("year", ""),
                        "device_label": label,
                        "dye": label if label else meta.get("dye", ""),
                        "semiconductor": meta.get("semiconductor", ""),
                        "electrolyte": meta.get("electrolyte", ""),
                        "substrate": meta.get("substrate", ""),
                        "active_area": meta.get("active_area", ""),
                        "solar_simulator": meta.get("solar_simulator", ""),
                        "voc": match.group("voc"),
                        "voc_units": match.group("voc_units"),
                        "jsc": match.group("jsc"),
                        "jsc_units": match.group("jsc_units"),
                        "ff": match.group("ff"),
                        "pce_percent": match.group("pce"),
                        "paper_title": meta.get("paper_title", ""),
                        "doi": meta.get("doi", ""),
                        "journal": meta.get("journal", ""),
                        "source_url": meta.get("source_url", ""),
                        "local_file": str(path),
                        "property_context": context(text, match.start(), match.end()),
                        "validation_status": "text_core_properties_extracted_needs_manual_validation",
                    }
                )
    fields = [
        "year", "device_label", "dye", "semiconductor", "electrolyte", "substrate",
        "active_area", "solar_simulator", "voc", "voc_units", "jsc", "jsc_units",
        "ff", "pce_percent", "paper_title", "doi", "journal", "source_url",
        "local_file", "property_context", "validation_status",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"records={len(rows)}")
    print(f"output={OUTPUT}")
    print(f"papers={len(set(r['local_file'] for r in rows))}")


if __name__ == "__main__":
    main()
