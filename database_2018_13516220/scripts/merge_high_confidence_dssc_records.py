#!/usr/bin/env python3
"""Merge high-confidence DSSC records from table and core-property extractors."""

import csv
from pathlib import Path


BASE = Path("database_2018_13516220/doaj_2020_2026/scraped")
INPUTS = [
    ("html_table", BASE / "green_dssc_table_records_2020_2026.csv"),
    ("pdf_table", BASE / "green_dssc_pdf_table_records_2020_2026.csv"),
    ("text_core_props", BASE / "green_dssc_text_records_with_core_properties_2020_2026.csv"),
]
OUTPUT = BASE / "green_dssc_high_confidence_records_2020_2026.csv"

FIELDS = [
    "extraction_source", "year", "device_label", "dye", "semiconductor", "electrolyte",
    "substrate", "active_area", "solar_simulator", "voc", "voc_units", "jsc",
    "jsc_units", "ff", "pce_percent", "paper_title", "doi", "journal", "source_url",
    "local_file", "context_or_table", "validation_status",
]


def clean(value):
    return " ".join((value or "").split())


def load_rows(source, path):
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            context = row.get("property_context") or row.get("table_row_raw") or row.get("table_caption") or ""
            rows.append(
                {
                    "extraction_source": source,
                    "year": row.get("year", ""),
                    "device_label": row.get("device_label", ""),
                    "dye": row.get("dye", ""),
                    "semiconductor": row.get("semiconductor", ""),
                    "electrolyte": row.get("electrolyte", ""),
                    "substrate": row.get("substrate", ""),
                    "active_area": row.get("active_area", ""),
                    "solar_simulator": row.get("solar_simulator", ""),
                    "voc": row.get("voc", ""),
                    "voc_units": row.get("voc_units", ""),
                    "jsc": row.get("jsc", ""),
                    "jsc_units": row.get("jsc_units", ""),
                    "ff": row.get("ff", ""),
                    "pce_percent": row.get("pce_percent", ""),
                    "paper_title": row.get("paper_title", ""),
                    "doi": row.get("doi", ""),
                    "journal": row.get("journal", ""),
                    "source_url": row.get("source_url", ""),
                    "local_file": row.get("local_file", ""),
                    "context_or_table": context,
                    "validation_status": row.get("validation_status", ""),
                }
            )
    return rows


def main():
    rows = []
    for source, path in INPUTS:
        rows.extend(load_rows(source, path))

    seen = set()
    deduped = []
    for row in rows:
        key = (
            clean(row["doi"]).lower(),
            clean(row["device_label"]).lower(),
            clean(row["dye"]).lower(),
            clean(row["voc"]),
            clean(row["jsc"]),
            clean(row["ff"]),
            clean(row["pce_percent"]),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    deduped.sort(key=lambda r: (r["year"], r["doi"], r["extraction_source"], r["device_label"], r["dye"]))

    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(deduped)

    print(f"records={len(deduped)}")
    print(f"output={OUTPUT}")
    print(f"papers={len(set(r['doi'] or r['local_file'] for r in deduped))}")
    for source, _path in INPUTS:
        print(f"{source}={sum(1 for r in deduped if r['extraction_source'] == source)}")


if __name__ == "__main__":
    main()
