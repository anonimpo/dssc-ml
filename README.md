# DSSC Green Materials Dataset

This repository contains scripts and curated outputs for building a high-confidence dye-sensitized solar cell (DSSC) dataset focused on green or environmentally friendly materials from 2020-2026 literature.

## Main Outputs

- `database_2018_13516220/doaj_2020_2026/scraped/green_dssc_high_confidence_records_2020_2026.csv`
- `database_2018_13516220/doaj_2020_2026/scraped/green_dssc_curated_for_ml_2020_2026.csv`
- `database_2018_13516220/doaj_2020_2026/scraped/green_dssc_virtual_combinations_2020_2026.csv`
- `database_2018_13516220/doaj_2020_2026/scraped/high_confidence_ml_dft_workflow.md`

## Workflow

The workflow follows a literature-mining to ML/DFT preparation path:

1. Fetch DOAJ DSSC metadata from 2020-2026.
2. Scrape available full text and PDF sources.
3. Extract DSSC fields: dye, semiconductor, electrolyte, substrate, active area, solar simulator, Voc, Jsc, FF, and PCE.
4. Keep high-confidence records where Voc, Jsc, FF, and PCE are present.
5. Curate records for ML input.
6. Generate virtual green material combinations for later feasibility checks, ML screening, and DFT.

Virtual combinations are not experimental measurements.

## Notes

Raw PDFs, HTML pages, local virtual environments, database dumps, and API keys are intentionally excluded from git.
