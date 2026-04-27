#!/usr/bin/env python3
"""Curate high-confidence DSSC records and create virtual green candidates."""

import csv
import re
from pathlib import Path


BASE = Path("database_2018_13516220/doaj_2020_2026/scraped")
INPUT = BASE / "green_dssc_high_confidence_records_2020_2026.csv"
CURATED = BASE / "green_dssc_curated_for_ml_2020_2026.csv"
COMBINATIONS = BASE / "green_dssc_virtual_combinations_2020_2026.csv"


NATURAL_TERMS = re.compile(
    r"pandan|anthocyanin|chlorophyll|curcumin|caulerpa|gymnogongrus|leaf|extract|natural|pigment",
    re.I,
)
METAL_FREE_ORGANIC_TERMS = re.compile(r"\bMS-1\b|\bMS-2\b|triazatruxene|metal-free|organic", re.I)
REFERENCE_DYE_TERMS = re.compile(r"\bN719\b|ruthenium|ru[- ]?based", re.I)
PT_FREE_TERMS = re.compile(r"carbon|graphene|rgo|fly ash|cuo|pani|polyaniline|pt[- ]?free", re.I)
SEMICONDUCTOR_TERMS = re.compile(r"TiO|SnO|ZnO|Ag", re.I)


def clean(value):
    return " ".join((value or "").replace("TIO", "TiO").split()).strip()


def first_number(value):
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value or "")
    return match.group(0) if match else ""


def to_float(value):
    num = first_number(value)
    try:
        return float(num) if num else None
    except ValueError:
        return None


def normalize_label(value):
    value = clean(value)
    value = re.sub(r"\bTiO\s+2\b", "TiO2", value)
    value = re.sub(r"\bTiO\s+(?=NP\b|NR\b|nanoparticle|nanorod)", "TiO2 ", value)
    value = re.sub(r"\bSnO\s+2\b", "SnO2", value)
    value = re.sub(r"\bNR-T\b", "nanorod treated", value)
    value = re.sub(r"\bNP\b", "nanoparticle", value)
    value = re.sub(r"\s+2$", "", value)
    return clean(value)


def normalize_electrolyte(value):
    value = clean(value)
    if re.search(r"iodide|tri[- ]?iodide|LiI|I\s*2\b|I-/I3", value, re.I):
        return "iodide/triiodide (LiI/I2)"
    if re.search(r"Cu|Co|redox", value, re.I) and len(value) < 80:
        return value
    return ""


def normalize_substrate(value):
    value = clean(value)
    if re.search(r"\bFTO\b|fluorine doped tin oxide", value, re.I):
        return "FTO glass"
    if re.search(r"\bITO\b", value, re.I):
        return "ITO glass"
    return value if len(value) <= 60 else ""


def material_class(row):
    text = " ".join([row.get("dye", ""), row.get("device_label", ""), row.get("semiconductor", ""), row.get("paper_title", "")])
    if REFERENCE_DYE_TERMS.search(text):
        return "reference_or_mixed_reference_dye"
    if METAL_FREE_ORGANIC_TERMS.search(text):
        return "metal_free_organic_dye"
    if NATURAL_TERMS.search(text):
        return "natural_or_biobased_dye"
    if PT_FREE_TERMS.search(text):
        return "pt_free_or_low_cost_component"
    return "green_relevance_needs_manual_check"


def curation_notes(row, cls):
    notes = []
    if row.get("validation_status", "").endswith("needs_manual_validation"):
        notes.append("check_against_original_paper")
    if "(" in row.get("pce_percent", "") or "(" in row.get("voc", ""):
        notes.append("value_contains_reported_replicate_or_sd")
    if not row.get("dye", ""):
        notes.append("dye_missing")
    if not row.get("semiconductor", "") or row.get("semiconductor") == "-":
        notes.append("semiconductor_missing")
    if cls == "reference_or_mixed_reference_dye":
        notes.append("not_primary_green_candidate")
    return "; ".join(notes)


def curate_rows():
    with INPUT.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    curated = []
    for row in rows:
        dye = normalize_label(row.get("dye") or row.get("device_label"))
        device_label = normalize_label(row.get("device_label", ""))
        semiconductor = normalize_label(row.get("semiconductor") or row.get("device_label"))
        if device_label and SEMICONDUCTOR_TERMS.search(device_label):
            semiconductor = device_label
        if semiconductor in {"-", "P-Tandem"}:
            semiconductor = ""
        cls = material_class(row)
        pce = to_float(row.get("pce_percent", ""))
        voc = to_float(row.get("voc", ""))
        jsc = to_float(row.get("jsc", ""))
        ff = to_float(row.get("ff", ""))

        curated.append(
            {
                "curation_status": "curated_candidate_needs_final_manual_check",
                "green_material_class": cls,
                "priority_for_ml_dft": priority(cls, pce),
                "year": row.get("year", ""),
                "dye_curated": dye,
                "semiconductor_curated": semiconductor,
                "electrolyte_curated": normalize_electrolyte(row.get("electrolyte", "")),
                "substrate_curated": normalize_substrate(row.get("substrate", "")),
                "active_area_curated": first_number(row.get("active_area", "")),
                "solar_simulator_curated": clean(row.get("solar_simulator", "")),
                "voc_numeric": voc if voc is not None else "",
                "jsc_numeric": jsc if jsc is not None else "",
                "ff_numeric": ff if ff is not None else "",
                "pce_percent_numeric": pce if pce is not None else "",
                "raw_voc": row.get("voc", ""),
                "raw_jsc": row.get("jsc", ""),
                "raw_ff": row.get("ff", ""),
                "raw_pce_percent": row.get("pce_percent", ""),
                "paper_title": row.get("paper_title", ""),
                "doi": row.get("doi", ""),
                "source_url": row.get("source_url", ""),
                "extraction_source": row.get("extraction_source", ""),
                "curation_notes": curation_notes(row, cls),
            }
        )
    return curated


def priority(cls, pce):
    if cls == "reference_or_mixed_reference_dye":
        return "low_reference_only"
    if pce is not None and pce >= 10:
        return "high"
    if cls in {"metal_free_organic_dye", "natural_or_biobased_dye"} and pce is not None and pce >= 0.1:
        return "medium"
    if cls in {"metal_free_organic_dye", "natural_or_biobased_dye"}:
        return "low_but_green"
    return "manual_review"


def unique_component(rows, field, allowed_classes=None):
    seen = {}
    for row in rows:
        if allowed_classes and row["green_material_class"] not in allowed_classes:
            continue
        value = clean(row.get(field, ""))
        if not value or value == "-":
            continue
        if value.lower() not in seen:
            seen[value.lower()] = {"value": value, "doi": row.get("doi", ""), "pce": row.get("pce_percent_numeric", "")}
    return list(seen.values())


def semiconductor_components(rows):
    components = unique_component(rows, "semiconductor_curated")
    return [item for item in components if SEMICONDUCTOR_TERMS.search(item["value"])]


def create_combinations(curated):
    dye_classes = {"metal_free_organic_dye", "natural_or_biobased_dye"}
    dyes = unique_component(curated, "dye_curated", dye_classes)
    semiconductors = semiconductor_components(curated)
    electrolytes = unique_component(curated, "electrolyte_curated")
    substrates = unique_component(curated, "substrate_curated")

    # Keep the combination set small and interpretable for the current dataset.
    semiconductors = semiconductors[:8]
    electrolytes = electrolytes[:3] or [{"value": "iodide/triiodide", "doi": "general_dssc_default", "pce": ""}]
    substrates = substrates[:2] or [{"value": "FTO", "doi": "general_dssc_default", "pce": ""}]

    combos = []
    for dye in dyes:
        for semiconductor in semiconductors:
            for electrolyte in electrolytes:
                for substrate in substrates:
                    if len(combos) >= 80:
                        return combos
                    source_dois = sorted({dye["doi"], semiconductor["doi"], electrolyte["doi"], substrate["doi"]})
                    combos.append(
                        {
                            "combination_status": "virtual_candidate_not_experimental",
                            "dye": dye["value"],
                            "semiconductor": semiconductor["value"],
                            "electrolyte": electrolyte["value"],
                            "substrate": substrate["value"],
                            "rationale": "green dye/material combined with high-confidence DSSC component pool",
                            "source_dois": "; ".join(d for d in source_dois if d),
                            "needs_next_step": "manual_feasibility_check_then_descriptor_or_dft_generation",
                        }
                    )
    return combos


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    curated = curate_rows()
    combinations = create_combinations(curated)

    curated_fields = [
        "curation_status", "green_material_class", "priority_for_ml_dft", "year",
        "dye_curated", "semiconductor_curated", "electrolyte_curated", "substrate_curated",
        "active_area_curated", "solar_simulator_curated", "voc_numeric", "jsc_numeric",
        "ff_numeric", "pce_percent_numeric", "raw_voc", "raw_jsc", "raw_ff",
        "raw_pce_percent", "paper_title", "doi", "source_url", "extraction_source",
        "curation_notes",
    ]
    combination_fields = [
        "combination_status", "dye", "semiconductor", "electrolyte", "substrate",
        "rationale", "source_dois", "needs_next_step",
    ]

    write_csv(CURATED, curated, curated_fields)
    write_csv(COMBINATIONS, combinations, combination_fields)

    print(f"curated_records={len(curated)}")
    print(f"curated_output={CURATED}")
    print(f"virtual_combinations={len(combinations)}")
    print(f"combination_output={COMBINATIONS}")


if __name__ == "__main__":
    main()
