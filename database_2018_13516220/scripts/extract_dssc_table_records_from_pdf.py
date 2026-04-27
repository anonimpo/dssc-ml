#!/usr/bin/env python3
"""Extract DSSC device records from tables in downloaded DOAJ PDFs."""

import csv
import html
import re
from pathlib import Path

import pdfplumber


RAW_DIR = Path("database_2018_13516220/doaj_2020_2026/scraped/raw")
FULL_FIELDS = Path("database_2018_13516220/doaj_2020_2026/scraped/green_dssc_full_fields_2020_2026.csv")
DOAJ_ARTICLES = Path("database_2018_13516220/doaj_2020_2026/doaj_dssc_articles_2020_2026.csv")
OUTPUT = Path("database_2018_13516220/doaj_2020_2026/scraped/green_dssc_pdf_table_records_2020_2026.csv")
TABLE_LOG = Path("database_2018_13516220/doaj_2020_2026/scraped/pdf_table_extraction_log.csv")

PROPERTY_RE = re.compile(
    r"\b(Voc|V\s*OC|V_oc|open[- ]?circuit|Jsc|J\s*SC|J_sc|short[- ]?circuit|"
    r"fill factor|FF|PCE|η|efficiency|power conversion)",
    re.I,
)


def clean(value):
    value = html.unescape(value or "")
    value = value.replace("\n", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def norm(value):
    value = clean(value).lower()
    value = value.replace("η", "eta")
    value = re.sub(r"[^a-z0-9%]+", " ", value)
    return value.strip()


def strip_value(value):
    value = clean(value)
    match = re.search(r"[-+]?\d+(?:\.\d+)?(?:\s*\([^)]*\))?", value)
    return match.group(0) if match else value


def numericish(value):
    value = clean(value)
    return bool(re.search(r"[-+]?\d+(?:\.\d+)?", value))


def rows_from_pdf_table(table):
    rows = []
    for row in table or []:
        cells = [clean(cell) for cell in row]
        while cells and not cells[-1]:
            cells.pop()
        if any(cells):
            rows.append(cells)
    return rows


def property_key(label):
    h = norm(label)
    if re.search(r"\bvoc\b|\bv oc\b|\bv\b.*\boc\b|open circuit", h):
        return "voc"
    if re.search(r"\bjsc\b|\bj sc\b|\bj\b.*\bsc\b|short circuit|current density", h):
        return "jsc"
    if re.search(r"\bff|fill factor", h):
        return "ff"
    if re.search(r"\bpce|efficiency|power conversion|\beta\b", h):
        return "pce_percent"
    if re.search(r"\barea\b", h):
        return "active_area"
    return ""


def header_map(headers):
    mapping = {}
    for index, header in enumerate(headers):
        h = norm(header)
        key = property_key(header)
        if key:
            mapping[key] = index
        elif re.search(r"\bdye\b|sensiti[sz]er|pigment|extract|source", h):
            mapping["dye"] = index
        elif re.search(r"semiconductor|photoanode|electrode|sample|device|tio2|zno|sno2|graphene|rgo", h):
            mapping.setdefault("device_label", index)
            mapping.setdefault("semiconductor", index)
        elif re.search(r"electrolyte|redox", h):
            mapping["electrolyte"] = index
        elif re.search(r"substrate|fto|ito", h):
            mapping["substrate"] = index
        elif re.search(r"illumination|irradiance|solar|am 1 5|sun", h):
            mapping["solar_simulator"] = index
        elif index == 0:
            mapping.setdefault("device_label", index)
    return mapping


def choose_header(rows):
    for index, row in enumerate(rows[:8]):
        if PROPERTY_RE.search(" ".join(row)):
            return index, row
    return 0, rows[0] if rows else []


def get(row, mapping, key):
    index = mapping.get(key)
    if index is None or index >= len(row):
        return ""
    return clean(row[index])


def property_count(record):
    return sum(bool(record.get(k)) for k in ["voc", "jsc", "ff", "pce_percent"])


def record_is_plausible(record):
    if property_count(record) < 2:
        return False
    if record.get("pce_percent"):
        try:
            pce = float(re.search(r"[-+]?\d+(?:\.\d+)?", record["pce_percent"]).group(0))
            if not 0 < pce <= 60:
                return False
        except Exception:
            return False
    return True


def metadata_by_path():
    meta = {}
    by_doi = {}
    if FULL_FIELDS.exists():
        with FULL_FIELDS.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                path = row.get("local_file", "")
                if path and path not in meta:
                    meta[path] = row
                doi = row.get("doi", "")
                if doi and doi not in by_doi:
                    by_doi[doi] = row
    if DOAJ_ARTICLES.exists():
        with DOAJ_ARTICLES.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                doi = row.get("doi", "")
                if doi and doi not in by_doi:
                    by_doi[doi] = {
                        "year": row.get("year", ""),
                        "paper_title": row.get("title", ""),
                        "doi": doi,
                        "journal": row.get("journal", ""),
                        "source_url": row.get("pdf_url") or row.get("fulltext_url", ""),
                    }
    return meta, by_doi


def doi_to_stem(doi):
    return clean(doi).replace("/", "_").replace(":", "_")


def metadata_for_pdf(path, meta, by_doi):
    path = Path(path)
    base = meta.get(str(path), {}) or meta.get(str(path.with_suffix(".html")), {})
    if base:
        return base
    for doi, row in by_doi.items():
        if doi_to_stem(doi) == path.stem:
            return row
    return {}


def table_is_transposed(rows):
    if len(rows) < 3:
        return False
    first_col_keys = [property_key(row[0]) for row in rows[1:] if row]
    return sum(bool(key) for key in first_col_keys) >= 3


def records_from_transposed(rows, base, path, page_number, table_index):
    device_labels = rows[0][1:]
    props = {}
    for row in rows[1:]:
        if len(row) < 2:
            continue
        key = property_key(row[0])
        if key:
            props[key] = row[1:]

    records = []
    for col_index, label in enumerate(device_labels):
        def pget(key):
            values = props.get(key, [])
            return strip_value(values[col_index]) if col_index < len(values) else ""

        record = {
            "year": base.get("year", ""),
            "device_label": clean(label),
            "dye": base.get("dye", ""),
            "semiconductor": clean(label) or base.get("semiconductor", ""),
            "electrolyte": base.get("electrolyte", ""),
            "substrate": base.get("substrate", ""),
            "active_area": pget("active_area") or base.get("active_area", ""),
            "solar_simulator": base.get("solar_simulator", ""),
            "voc": pget("voc"),
            "jsc": pget("jsc"),
            "ff": pget("ff"),
            "pce_percent": pget("pce_percent"),
            "table_caption": f"PDF page {page_number}, table {table_index}",
            "table_headers": " | ".join(rows[0]),
            "table_row_raw": " || ".join(" | ".join(row) for row in rows),
            "paper_title": base.get("paper_title", ""),
            "doi": base.get("doi", ""),
            "journal": base.get("journal", ""),
            "source_url": base.get("source_url", ""),
            "local_file": str(path),
            "validation_status": "pdf_table_extracted_needs_manual_validation",
        }
        if record_is_plausible(record):
            records.append(record)
    return records


def records_from_normal(rows, base, path, page_number, table_index):
    header_index, headers = choose_header(rows)
    mapping = header_map(headers)
    if not any(key in mapping for key in ["voc", "jsc", "ff", "pce_percent"]):
        return []

    records = []
    for data_row in rows[header_index + 1 :]:
        record = {
            "year": base.get("year", ""),
            "device_label": get(data_row, mapping, "device_label"),
            "dye": get(data_row, mapping, "dye") or base.get("dye", ""),
            "semiconductor": get(data_row, mapping, "semiconductor") or base.get("semiconductor", ""),
            "electrolyte": get(data_row, mapping, "electrolyte") or base.get("electrolyte", ""),
            "substrate": get(data_row, mapping, "substrate") or base.get("substrate", ""),
            "active_area": get(data_row, mapping, "active_area") or base.get("active_area", ""),
            "solar_simulator": get(data_row, mapping, "solar_simulator") or base.get("solar_simulator", ""),
            "voc": strip_value(get(data_row, mapping, "voc")),
            "jsc": strip_value(get(data_row, mapping, "jsc")),
            "ff": strip_value(get(data_row, mapping, "ff")),
            "pce_percent": strip_value(get(data_row, mapping, "pce_percent")),
            "table_caption": f"PDF page {page_number}, table {table_index}",
            "table_headers": " | ".join(headers),
            "table_row_raw": " | ".join(data_row),
            "paper_title": base.get("paper_title", ""),
            "doi": base.get("doi", ""),
            "journal": base.get("journal", ""),
            "source_url": base.get("source_url", ""),
            "local_file": str(path),
            "validation_status": "pdf_table_extracted_needs_manual_validation",
        }
        if record_is_plausible(record) and any(numericish(record[k]) for k in ["voc", "jsc", "ff", "pce_percent"]):
            records.append(record)
    return records


def main():
    meta, by_doi = metadata_by_path()
    records = []
    logs = []

    for path in sorted(RAW_DIR.glob("*.pdf")):
        base = metadata_for_pdf(path, meta, by_doi)
        total_tables = 0
        pv_tables = 0
        before = len(records)
        status = "ok"
        try:
            with pdfplumber.open(path) as pdf:
                for page_number, page in enumerate(pdf.pages, 1):
                    for table_index, table in enumerate(page.extract_tables() or [], 1):
                        total_tables += 1
                        rows = rows_from_pdf_table(table)
                        if len(rows) < 2 or not PROPERTY_RE.search(" ".join(" ".join(row) for row in rows)):
                            continue
                        if table_is_transposed(rows):
                            extracted = records_from_transposed(rows, base, path, page_number, table_index)
                        else:
                            extracted = records_from_normal(rows, base, path, page_number, table_index)
                        if extracted:
                            pv_tables += 1
                            records.extend(extracted)
        except Exception as exc:
            status = f"error:{type(exc).__name__}"

        logs.append(
            {
                "local_file": str(path),
                "doi": base.get("doi", ""),
                "title": base.get("paper_title", ""),
                "tables": total_tables,
                "pv_tables": pv_tables,
                "records": len(records) - before,
                "status": status,
            }
        )

    seen = set()
    deduped = []
    for record in records:
        key = (
            record.get("doi"),
            record.get("device_label"),
            record.get("voc"),
            record.get("jsc"),
            record.get("ff"),
            record.get("pce_percent"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)

    fields = [
        "year", "device_label", "dye", "semiconductor", "electrolyte", "substrate",
        "active_area", "solar_simulator", "voc", "jsc", "ff", "pce_percent",
        "table_caption", "table_headers", "table_row_raw", "paper_title", "doi",
        "journal", "source_url", "local_file", "validation_status",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(deduped)

    with TABLE_LOG.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["local_file", "doi", "title", "tables", "pv_tables", "records", "status"])
        writer.writeheader()
        writer.writerows(logs)

    print(f"records={len(deduped)}")
    print(f"output={OUTPUT}")
    print(f"log={TABLE_LOG}")
    print(f"papers_with_records={len(set(r['doi'] or r['local_file'] for r in deduped))}")


if __name__ == "__main__":
    main()
