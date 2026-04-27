#!/usr/bin/env python3
"""Scrape DOAJ paper links and extract green DSSC material candidates.

This is a pragmatic text-mining pass over open metadata/full text. It does not
try to reproduce the original ChemDataExtractor pipeline; it creates a review
table for manual curation and follow-up extraction.
"""

import argparse
import csv
import html
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


GREEN_TERMS = re.compile(
    r"\b(natural|bio[- ]?based|biomass|biosynthesi[sz]ed|green synthesis|"
    r"eco[- ]?friendly|plant|leaf|leaves|flower|fruit|extract|pigment|"
    r"anthocyanin|chlorophyll|betalain|bixin|curcumin|metal[- ]?free|"
    r"pt[- ]?free|platinum[- ]?free|carbon|biochar|rgo|graphene|polyaniline|"
    r"pedot|counter electrode|low[- ]?toxic|sustainable)\b",
    re.I,
)

EXCLUDE_TERMS = re.compile(r"\b(N719|N3|Ru[- ]?based|ruthenium|lead|PbI3|CdS)\b", re.I)

MATERIAL_PATTERNS = [
    r"\bTiO2\b",
    r"\bZnO\b",
    r"\bSnO2\b",
    r"\bNiO\b",
    r"\bCuO\b",
    r"\bFe2O3\b",
    r"\bhematite\b",
    r"\bCeO2\b",
    r"\bNb2O5\b",
    r"\bpolyaniline\b|\bPANI\b",
    r"\bPEDOT:PSS\b",
    r"\brGO\b|\breduced graphene oxide\b",
    r"\bgraphene\b",
    r"\bcarbon\b|\bbiochar\b",
    r"\banthocyanin\w*\b",
    r"\bchlorophyll\w*\b",
    r"\bbetalain\w*\b",
    r"\bbixin\b|\bnorbixin\b",
    r"\bcurcumin\b|\bturmeric\b",
    r"\bpomegranate\b",
    r"\bteak leaves\b",
    r"\bDelonix regia\b",
    r"\bTagetes erecta\b|\bmarigold\b",
    r"\bHibiscus sabdariffa\b",
    r"\bBrassica napus\b|\bmustard flower\b",
    r"\bPandan leaf\b",
    r"\boyster mushroom\b",
    r"\bSpirulina\b|\bChlorella\b",
    r"\bCaulerpa racemose\b|\bGymnogongrus flabelliformis\b",
    r"\bMoringa oleifera\b",
    r"\bMurraya koenigii\b",
    r"\bEuphorbia milii\b",
    r"\bCassia siamea\b|\bAcacia\b",
    r"\bAverrhoa bilimbi\b",
    r"\bLonchocarpus cyanescens\b",
    r"\bP\.?\s*pterocarpum\b",
]

PERFORMANCE_PATTERN = re.compile(
    r"(?:(?:PCE|power conversion efficiency|efficiency|η)\D{0,40})"
    r"(\d+(?:\.\d+)?)\s?%",
    re.I,
)


def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def first_url(value):
    if not value:
        return ""
    return value.split(";")[0].strip()


def candidate_url(row):
    pdf = first_url(row.get("pdf_url", ""))
    fulltext = first_url(row.get("fulltext_url", ""))
    if pdf:
        return pdf
    if "mdpi.com" in fulltext and "/pdf" not in fulltext:
        return fulltext.rstrip("/") + "/pdf"
    return fulltext


def safe_name(row, idx):
    doi = re.sub(r"[^A-Za-z0-9_.-]+", "_", row.get("doi") or "")
    if doi:
        return doi[:120]
    title = re.sub(r"[^A-Za-z0-9_.-]+", "_", clean_text(row.get("title", "")))
    return f"{idx:03d}_{title[:80]}"


def fetch(url, out_path, timeout=50):
    headers = {"User-Agent": "dssc-green-material-scraper/1.0"}
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        data = response.read()
        content_type = response.headers.get("Content-Type", "")
        final_url = response.geturl()
    out_path.write_bytes(data)
    return content_type, final_url, len(data)


def html_to_text(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return clean_text(text)


def pdf_to_text(path):
    try:
        result = subprocess.run(
            ["pdftotext", str(path), "-"],
            check=True,
            text=True,
            capture_output=True,
            timeout=60,
        )
        return clean_text(result.stdout)
    except Exception:
        return ""


def extract_materials(text):
    found = []
    for pattern in MATERIAL_PATTERNS:
        for match in re.finditer(pattern, text, re.I):
            material = clean_text(match.group(0))
            if material and material.lower() not in [x.lower() for x in found]:
                found.append(material)
    return found


def classify_role(material, text):
    material_l = material.lower()
    if any(x in material_l for x in ["anthocyan", "chlorophyll", "betalain", "bixin", "curcumin", "pomegranate", "teak", "regia", "tagetes", "hibiscus", "brassica", "pandan", "mushroom", "spirulina", "chlorella", "caulerpa", "gymnogongrus", "euphorbia", "lonchocarpus", "pterocarpum"]):
        return "sensitizer_dye"
    if any(x in material_l for x in ["carbon", "graphene", "rgo", "polyaniline", "pani", "pedot", "nio", "cuo", "hematite", "fe2o3"]):
        return "counter_electrode_or_additive"
    if any(x in material_l for x in ["tio2", "zno", "sno2", "ceo2", "nb2o5"]):
        return "photoanode_semiconductor"
    if "counter electrode" in text.lower():
        return "counter_electrode"
    return "material_candidate"


def best_performance(text):
    snippets = []
    values = []
    for match in PERFORMANCE_PATTERN.finditer(text):
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if not (0 < value <= 50):
            continue
        values.append(value)
        start = max(0, match.start() - 120)
        end = min(len(text), match.end() + 120)
        snippet = clean_text(text[start:end])
        if snippet not in snippets:
            snippets.append(snippet)
    return (max(values) if values else ""), " | ".join(snippets[:4])


def relevance(row):
    text = clean_text(" ".join([row.get("title", ""), row.get("abstract", ""), row.get("keywords", "")]))
    score = 0
    score += 3 if GREEN_TERMS.search(text) else 0
    score += 2 if re.search(r"\bDSSC|dye[- ]sensiti[sz]ed solar cell", text, re.I) else 0
    score -= 2 if EXCLUDE_TERMS.search(text) else 0
    return score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="database_2018_13516220/doaj_2020_2026/doaj_dssc_articles_2020_2026.csv")
    parser.add_argument("--out-dir", default="database_2018_13516220/doaj_2020_2026/scraped")
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--sleep", type=float, default=0.5)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "green_dssc_materials_from_doaj_2020_2026.csv"
    log_csv = out_dir / "scrape_log.csv"

    with open(args.input, encoding="utf-8") as handle:
        all_rows = list(csv.DictReader(handle))
    selected = [r for r in all_rows if relevance(r) >= 3 and candidate_url(r)]
    selected.sort(key=lambda r: (int(r.get("year") or 0), relevance(r)), reverse=True)
    selected = selected[: args.limit]

    material_rows = []
    log_rows = []
    for idx, row in enumerate(selected, 1):
        url = candidate_url(row)
        stem = safe_name(row, idx)
        suffix = ".pdf" if ".pdf" in url.lower() or "/pdf" in url.lower() else ".html"
        raw_path = raw_dir / f"{stem}{suffix}"
        status = "ok"
        text = clean_text(" ".join([row.get("title", ""), row.get("abstract", ""), row.get("keywords", "")]))
        final_url = url
        content_type = ""
        size = 0
        try:
            if not raw_path.exists():
                content_type, final_url, size = fetch(url, raw_path)
                time.sleep(args.sleep)
            if raw_path.suffix == ".pdf" or raw_path.read_bytes()[:4] == b"%PDF":
                text = clean_text(text + " " + pdf_to_text(raw_path))
            else:
                text = clean_text(text + " " + html_to_text(raw_path))
        except Exception as exc:
            status = f"error:{exc.__class__.__name__}"

        materials = extract_materials(text)
        max_pce, performance_snippets = best_performance(text)
        if not materials and GREEN_TERMS.search(text):
            materials = ["green_material_mentioned"]

        for material in materials:
            material_rows.append(
                {
                    "year": row.get("year", ""),
                    "material": material,
                    "role": classify_role(material, text),
                    "max_pce_percent_text_mined": max_pce,
                    "paper_title": clean_text(row.get("title", "")),
                    "doi": row.get("doi", ""),
                    "journal": row.get("journal", ""),
                    "source_url": final_url,
                    "local_file": str(raw_path),
                    "performance_snippets": performance_snippets,
                    "green_basis": "matches green/natural/bio/metal-free/Pt-free screening terms",
                }
            )

        log_rows.append(
            {
                "status": status,
                "year": row.get("year", ""),
                "title": clean_text(row.get("title", "")),
                "doi": row.get("doi", ""),
                "url": url,
                "final_url": final_url,
                "content_type": content_type,
                "bytes": size,
                "materials_found": len(materials),
            }
        )

    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "year",
            "material",
            "role",
            "max_pce_percent_text_mined",
            "paper_title",
            "doi",
            "journal",
            "source_url",
            "local_file",
            "performance_snippets",
            "green_basis",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(material_rows)

    with log_csv.open("w", newline="", encoding="utf-8") as handle:
        fields = ["status", "year", "title", "doi", "url", "final_url", "content_type", "bytes", "materials_found"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(log_rows)

    print(f"selected={len(selected)}")
    print(f"materials={len(material_rows)}")
    print(f"out_csv={out_csv}")
    print(f"log_csv={log_csv}")


if __name__ == "__main__":
    main()
