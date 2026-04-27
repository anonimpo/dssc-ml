#!/usr/bin/env python3
"""Extract DSSC records from HTML tables in scraped DOAJ papers.

This complements the broader text-mining CSV by only using semi-structured
HTML tables whose headers/cells mention photovoltaic properties.
"""

import csv
import html
import re
from pathlib import Path

from bs4 import BeautifulSoup


SCRAPE_LOG = Path("database_2018_13516220/doaj_2020_2026/scraped/scrape_log.csv")
FULL_FIELDS = Path("database_2018_13516220/doaj_2020_2026/scraped/green_dssc_full_fields_2020_2026.csv")
OUTPUT = Path("database_2018_13516220/doaj_2020_2026/scraped/green_dssc_table_records_2020_2026.csv")
TABLE_LOG = Path("database_2018_13516220/doaj_2020_2026/scraped/table_extraction_log.csv")

PROPERTY_RE = re.compile(
    r"\b(Voc|V_oc|open[- ]?circuit|Jsc|J_sc|short[- ]?circuit|fill factor|FF|"
    r"PCE|η|efficiency|power conversion)\b",
    re.I,
)


def clean(value):
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def norm(value):
    value = clean(value).lower()
    value = value.replace("η", "eta")
    value = re.sub(r"[^a-z0-9%]+", " ", value)
    return value.strip()


def cell_text(cell):
    return clean(cell.get_text(" ", strip=True))


def table_caption(table):
    parent = table.find_parent(["table-wrap", "figure", "div"])
    parts = []
    if parent:
        for tag in parent.find_all(["label", "caption"], recursive=False):
            parts.append(cell_text(tag))
        cap = parent.find("caption")
        if cap:
            parts.append(cell_text(cap))
    cap = table.find("caption")
    if cap:
        parts.append(cell_text(cap))
    return " ".join(unique(parts))


def unique(items):
    out = []
    for item in items:
        item = clean(item)
        if item and item.lower() not in [x.lower() for x in out]:
            out.append(item)
    return out


def extract_rows(table):
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if cells:
            rows.append([cell_text(c) for c in cells])
    return [r for r in rows if any(r)]


def choose_header(rows):
    for idx, row in enumerate(rows[:6]):
        if PROPERTY_RE.search(" ".join(row)):
            return idx, row
    return 0, rows[0] if rows else []


def header_map(headers):
    mapping = {}
    for i, header in enumerate(headers):
        h = norm(header)
        if re.search(r"\bvoc\b|open circuit", h):
            mapping["voc"] = i
        elif re.search(r"\bjsc\b|short circuit current density|current density", h):
            mapping["jsc"] = i
        elif re.search(r"\bff\b|fill factor", h):
            mapping["ff"] = i
        elif re.search(r"\bpce\b|efficiency|power conversion|eta", h):
            mapping["pce_percent"] = i
        elif re.search(r"\bdye\b|sensiti[sz]er|pigment|extract", h):
            mapping["dye"] = i
        elif re.search(r"semiconductor|photoanode|electrode|tio2|zno|sno2", h):
            mapping["semiconductor"] = i
        elif re.search(r"electrolyte|redox", h):
            mapping["electrolyte"] = i
        elif re.search(r"substrate|fto|ito", h):
            mapping["substrate"] = i
        elif re.search(r"area", h):
            mapping["active_area"] = i
        elif re.search(r"illumination|irradiance|solar|am 1 5|sun", h):
            mapping["solar_simulator"] = i
        elif i == 0:
            mapping.setdefault("device_label", i)
    return mapping


def property_key(label):
    h = norm(label)
    if re.search(r"\bvoc\b|open circuit", h):
        return "voc"
    if re.search(r"\bjsc\b|short circuit current density|current density", h):
        return "jsc"
    if re.search(r"\bff\b|fill factor", h):
        return "ff"
    if re.search(r"\bpce\b|efficiency|power conversion|eta", h):
        return "pce_percent"
    if re.search(r"\barea\b", h):
        return "active_area"
    return ""


def is_transposed_property_table(rows):
    if len(rows) < 3:
        return False
    first_col_keys = [property_key(r[0]) for r in rows[1:] if r]
    return sum(bool(k) for k in first_col_keys) >= 3


def records_from_transposed(rows, base, source, doi, path, caption, table_index):
    if not rows or len(rows[0]) < 2:
        return []
    device_labels = rows[0][1:]
    props = {}
    for row in rows[1:]:
        if len(row) < 2:
            continue
        key = property_key(row[0])
        if key:
            props[key] = row[1:]
    out = []
    for col_idx, label in enumerate(device_labels):
        def pget(key):
            values = props.get(key, [])
            return values[col_idx] if col_idx < len(values) else ""

        semiconductor = clean(label) or base.get("semiconductor", "")
        if base.get("semiconductor"):
            semiconductor = clean(label) + "; " + base.get("semiconductor", "") if label else base.get("semiconductor", "")
        out.append(
            {
                "year": base.get("year", ""),
                "device_label": clean(label),
                "dye": base.get("dye", ""),
                "semiconductor": semiconductor,
                "electrolyte": base.get("electrolyte", ""),
                "substrate": base.get("substrate", ""),
                "active_area": pget("active_area") or base.get("active_area", ""),
                "solar_simulator": base.get("solar_simulator", ""),
                "voc": pget("voc"),
                "jsc": pget("jsc"),
                "ff": pget("ff"),
                "pce_percent": pget("pce_percent"),
                "table_caption": caption,
                "table_headers": " | ".join(rows[0]),
                "table_row_raw": " || ".join(" | ".join(r) for r in rows),
                "paper_title": base.get("paper_title") or source.get("title", ""),
                "doi": doi,
                "journal": base.get("journal", ""),
                "source_url": base.get("source_url", source.get("url", "")),
                "local_file": path,
                "validation_status": "html_table_extracted_needs_manual_validation",
            }
        )
    return out


def get(row, mapping, key):
    idx = mapping.get(key)
    if idx is None or idx >= len(row):
        return ""
    return row[idx]


def metadata_by_local_file():
    meta = {}
    if FULL_FIELDS.exists():
        with FULL_FIELDS.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                path = row.get("local_file", "")
                if path and path not in meta:
                    meta[path] = row
    return meta


def log_rows():
    rows = []
    if SCRAPE_LOG.exists():
        with SCRAPE_LOG.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    return rows


def row_has_property(row, mapping):
    return any(get(row, mapping, key) for key in ["voc", "jsc", "ff", "pce_percent"])


def main():
    meta = metadata_by_local_file()
    records = []
    logs = []

    for source in log_rows():
        local = source.get("final_url", "")
        path = ""
        # The scrape log does not store local path, so recover by DOI stem via full field metadata.
        doi = source.get("doi", "")
        for p, row in meta.items():
            if row.get("doi") == doi:
                path = p
                break
        if not path or not path.endswith(".html") or not Path(path).exists():
            logs.append({"doi": doi, "title": source.get("title", ""), "tables": 0, "pv_tables": 0, "records": 0, "status": "no_html"})
            continue

        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(text, "lxml")
        tables = soup.find_all("table")
        pv_tables = 0
        before_count = len(records)

        for table_index, table in enumerate(tables, 1):
            table_text = cell_text(table)
            if not PROPERTY_RE.search(table_text):
                continue
            rows = extract_rows(table)
            if len(rows) < 2:
                continue
            caption = table_caption(table)
            base = meta.get(path, {})
            if is_transposed_property_table(rows):
                pv_tables += 1
                records.extend(records_from_transposed(rows, base, source, doi, path, caption, table_index))
                continue
            header_idx, headers = choose_header(rows)
            mapping = header_map(headers)
            if not any(k in mapping for k in ["voc", "jsc", "ff", "pce_percent"]):
                continue
            pv_tables += 1
            data_rows = rows[header_idx + 1 :]
            for data_row_index, data_row in enumerate(data_rows, 1):
                if not row_has_property(data_row, mapping):
                    continue
                dye = get(data_row, mapping, "dye") or base.get("dye", "")
                semiconductor = get(data_row, mapping, "semiconductor") or base.get("semiconductor", "")
                electrolyte = get(data_row, mapping, "electrolyte") or base.get("electrolyte", "")
                substrate = get(data_row, mapping, "substrate") or base.get("substrate", "")
                active_area = get(data_row, mapping, "active_area") or base.get("active_area", "")
                solar_simulator = get(data_row, mapping, "solar_simulator") or base.get("solar_simulator", "")
                records.append(
                    {
                        "year": base.get("year", ""),
                        "device_label": get(data_row, mapping, "device_label"),
                        "dye": dye,
                        "semiconductor": semiconductor,
                        "electrolyte": electrolyte,
                        "substrate": substrate,
                        "active_area": active_area,
                        "solar_simulator": solar_simulator,
                        "voc": get(data_row, mapping, "voc"),
                        "jsc": get(data_row, mapping, "jsc"),
                        "ff": get(data_row, mapping, "ff"),
                        "pce_percent": get(data_row, mapping, "pce_percent"),
                        "table_caption": caption,
                        "table_headers": " | ".join(headers),
                        "table_row_raw": " | ".join(data_row),
                        "paper_title": base.get("paper_title") or source.get("title", ""),
                        "doi": doi,
                        "journal": base.get("journal", ""),
                        "source_url": base.get("source_url", source.get("url", "")),
                        "local_file": path,
                        "validation_status": "html_table_extracted_needs_manual_validation",
                    }
                )

        logs.append(
            {
                "doi": doi,
                "title": source.get("title", ""),
                "tables": len(tables),
                "pv_tables": pv_tables,
                "records": len(records) - before_count,
                "status": "ok",
            }
        )

    fields = [
        "year", "device_label", "dye", "semiconductor", "electrolyte", "substrate",
        "active_area", "solar_simulator", "voc", "jsc", "ff", "pce_percent",
        "table_caption", "table_headers", "table_row_raw", "paper_title", "doi",
        "journal", "source_url", "local_file", "validation_status",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

    with TABLE_LOG.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["doi", "title", "tables", "pv_tables", "records", "status"])
        writer.writeheader()
        writer.writerows(logs)

    print(f"records={len(records)}")
    print(f"output={OUTPUT}")
    print(f"log={TABLE_LOG}")
    print(f"papers_with_records={len(set(r['doi'] for r in records))}")


if __name__ == "__main__":
    main()
