#!/usr/bin/env python3
"""Build a fuller DSSC field table from scraped DOAJ papers.

Fields targeted:
Voc, Jsc, FF, PCE, dye, semiconductor, electrolyte, substrate, active area,
and solar simulator.

This is a text-mining pass for curation. It should be validated against paper
tables before being treated as final experimental data.
"""

import csv
import html
import re
import subprocess
from pathlib import Path


INPUT = Path("database_2018_13516220/doaj_2020_2026/scraped/green_dssc_materials_experimental_candidates_2020_2026.csv")
OUTPUT = Path("database_2018_13516220/doaj_2020_2026/scraped/green_dssc_full_fields_2020_2026.csv")

DYE_TERMS = [
    "pomegranate", "teak leaves", "Delonix regia", "Tagetes erecta", "marigold",
    "Hibiscus sabdariffa", "Brassica napus", "mustard flower", "Pandan leaf",
    "oyster mushroom", "Spirulina", "Chlorella", "Caulerpa racemose",
    "Gymnogongrus flabelliformis", "Moringa oleifera", "Murraya koenigii",
    "Euphorbia milii", "Cassia siamea", "Averrhoa bilimbi",
    "Lonchocarpus cyanescens", "P. pterocarpum", "P.pterocarpum",
    "Butea monosperma", "methyl orange", "methylene blue", "anthocyanin",
    "anthocyanins", "chlorophyll", "chlorophylls", "betalain", "betalains",
    "bixin", "norbixin", "curcumin", "turmeric",
]

SEMICONDUCTOR_TERMS = [
    "TiO2", "titanium dioxide", "ZnO", "zinc oxide", "SnO2", "tin oxide",
    "NiO", "CuO", "CeO2", "Nb2O5", "Fe2O3", "hematite", "Gd2Ru2O7",
]

SUBSTRATE_TERMS = [
    "FTO", "ITO", "fluorine doped tin oxide", "fluorine-doped tin oxide",
    "indium tin oxide", "glass", "conductive glass",
]

ELECTROLYTE_PATTERNS = [
    r"\bI3\s*[−-]\s*/\s*I\s*[−-]\b",
    r"\bI\s*[−-]\s*/\s*I3\s*[−-]\b",
    r"\bBr3\s*[−-]\s*/\s*I\s*[−-]\b",
    r"\bBr₃⁻/I⁻\b",
    r"\bI₃⁻/I⁻\b",
    r"\biodide/triiodide\b",
    r"\btriiodide/iodide\b",
    r"\belectrolyte[^.;]{0,120}",
]

SOLAR_PATTERNS = [
    r"(?:solar simulator|illumination|light intensity|irradiance)[^.;]{0,120}",
    r"\bAM\s*1\.5G?\b[^.;]{0,80}",
    r"\b100\s*mW\s*/?\s*cm(?:-2|\^?-?2|²)\b",
    r"\b1\s*sun\b",
]


def clean_text(value):
    value = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def read_raw(path):
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    try:
        if p.suffix.lower() == ".pdf" or p.read_bytes()[:4] == b"%PDF":
            result = subprocess.run(["pdftotext", str(p), "-"], check=True, text=True, capture_output=True, timeout=60)
            return clean_text(result.stdout)
        return clean_text(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return ""


def unique(items):
    out = []
    for item in items:
        item = clean_text(item)
        if item and item.lower() not in [x.lower() for x in out]:
            out.append(item)
    return out


def terms_found(terms, text):
    found = []
    for term in terms:
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", text, re.I):
            found.append(term)
    return unique(found)


def patterns_found(patterns, text, limit=5):
    found = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            found.append(match.group(0))
            if len(found) >= limit:
                return unique(found)
    return unique(found)


def first_match(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1), match.group(2) if len(match.groups()) > 1 else ""
    return "", ""


def all_pce(text):
    values = []
    for pattern in [
        r"(?:PCE|power conversion efficiency|efficiency|η)\D{0,45}(\d+(?:\.\d+)?)\s*%",
        r"(\d+(?:\.\d+)?)\s*%\D{0,35}(?:PCE|power conversion efficiency|efficiency)",
    ]:
        for match in re.finditer(pattern, text, re.I):
            try:
                value = float(match.group(1))
            except ValueError:
                continue
            if 0 < value <= 50:
                values.append(value)
    return values


def active_area(text):
    value, unit = first_match(
        [
            r"(?:active area|cell area|area)\D{0,35}(\d+(?:\.\d+)?)\s*(cm2|cm\^2|cm²|mm2|mm\^2|mm²)",
            r"(\d+(?:\.\d+)?)\s*(cm2|cm\^2|cm²|mm2|mm\^2|mm²)\D{0,35}(?:active area|cell area)",
        ],
        text,
    )
    return value, unit


def context(text):
    prop = re.compile(
        r"Voc|V_oc|open-circuit voltage|Jsc|J_sc|short-circuit current|fill factor|FF|PCE|"
        r"power conversion efficiency|efficiency|η|electrolyte|active area|solar simulator|AM\s*1\.5|100\s*mW",
        re.I,
    )
    snippets = []
    for match in prop.finditer(text):
        start = max(0, match.start() - 150)
        end = min(len(text), match.end() + 190)
        snippet = clean_text(text[start:end])
        if snippet and snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) >= 5:
            break
    return " | ".join(snippets)


def role_to_field(row, dyes, semiconductors):
    material = row["material"]
    role = row["role"]
    if role == "sensitizer_dye" and material not in dyes:
        dyes = unique([material] + dyes)
    if role == "photoanode_semiconductor" and material not in semiconductors:
        semiconductors = unique([material] + semiconductors)
    return dyes, semiconductors


def main():
    rows = list(csv.DictReader(INPUT.open(encoding="utf-8")))
    text_cache = {}
    out = []
    seen = set()

    for row in rows:
        key = (row["doi"], row["material"].lower(), row["role"])
        if key in seen:
            continue
        seen.add(key)

        path = row.get("local_file", "")
        if path not in text_cache:
            text_cache[path] = read_raw(path)
        text = clean_text(" ".join([row.get("performance_snippets", ""), row.get("paper_title", ""), text_cache[path]]))

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
        ff, ff_units = first_match([r"(?:fill factor|FF)\D{0,35}(\d+(?:\.\d+)?)\s*(%)?"], text)
        pces = all_pce(text)
        pce = row.get("max_pce_percent_text_mined", "")
        if not pce and pces:
            pce = str(max(pces))

        dyes = terms_found(DYE_TERMS, text)
        semiconductors = terms_found(SEMICONDUCTOR_TERMS, text)
        dyes, semiconductors = role_to_field(row, dyes, semiconductors)
        substrates = terms_found(SUBSTRATE_TERMS, text)
        electrolytes = patterns_found(ELECTROLYTE_PATTERNS, text)
        solar = patterns_found(SOLAR_PATTERNS, text)
        area_value, area_units = active_area(text)

        out.append(
            {
                "year": row["year"],
                "dye": "; ".join(dyes),
                "semiconductor": "; ".join(semiconductors),
                "electrolyte": "; ".join(electrolytes),
                "substrate": "; ".join(substrates),
                "active_area": area_value,
                "active_area_units": area_units,
                "solar_simulator": "; ".join(solar),
                "voc": voc,
                "voc_units": voc_units,
                "jsc": jsc,
                "jsc_units": jsc_units,
                "ff": ff,
                "ff_units": ff_units,
                "pce_percent": pce,
                "material": row["material"],
                "role": row["role"],
                "paper_title": row["paper_title"],
                "doi": row["doi"],
                "journal": row["journal"],
                "source_url": row["source_url"],
                "local_file": row["local_file"],
                "extraction_context": context(text),
                "validation_status": "text_mined_needs_table_validation",
            }
        )

    fields = [
        "year", "dye", "semiconductor", "electrolyte", "substrate",
        "active_area", "active_area_units", "solar_simulator",
        "voc", "voc_units", "jsc", "jsc_units", "ff", "ff_units", "pce_percent",
        "material", "role", "paper_title", "doi", "journal", "source_url",
        "local_file", "extraction_context", "validation_status",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)

    print(f"rows={len(out)}")
    print(f"output={OUTPUT}")
    for field in ["dye", "semiconductor", "electrolyte", "substrate", "active_area", "solar_simulator", "voc", "jsc", "ff", "pce_percent"]:
        print(f"with_{field}={sum(bool(r[field]) for r in out)}")


if __name__ == "__main__":
    main()
