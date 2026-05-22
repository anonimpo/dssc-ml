# High-Confidence Green DSSC Dataset Workflow

Main reference: Coppola et al., "A combined ML and DFT strategy for the prediction of dye candidates for indoor DSSCs", npj Computational Materials 11, 28 (2025), DOI: 10.1038/s41524-025-01521-9.

## Objective

Build a high-confidence dataset of environmentally friendly dye-sensitized solar cell (DSSC) materials from 2020-2026 papers, then prepare it for machine learning and DFT workflows following the general strategy of the reference paper.

Main dataset:

`green_dssc_high_confidence_records_2020_2026.csv`

## Workflow

1. Literature mining

   Papers are collected from DOAJ for the 2020-2026 period using DSSC-related keywords such as DSSC, natural dye, green synthesis, metal-free organic dye, bio-based dye, Pt-free counter electrode, and dye-sensitized solar cell.

2. Full-text scraping

   Paper metadata, HTML files, and PDFs are stored in `doaj_2020_2026/scraped/raw/`. This stage only collects candidate sources and is not treated as final validated data.

3. DSSC field extraction

   Extracted fields follow the ChemDataExtractor photovoltaic/DSSC schema:

   - dye
   - semiconductor
   - electrolyte
   - substrate
   - active area
   - solar simulator
   - Voc
   - Jsc
   - FF
   - PCE

4. High-confidence filtering

   A record is added to the main dataset only if it satisfies strong evidence criteria:

   - it comes from an HTML table, a PDF table, or a sentence containing complete core photovoltaic properties;
   - it contains all core properties: Voc, Jsc, FF, and PCE;
   - it has a clear DOI or paper source;
   - it is still marked as `needs_manual_validation` so the final values can be checked against the original paper.

5. Green/material relevance screening

   Candidates are prioritized if they match at least one of the following categories:

   - natural or bio-based dye;
   - metal-free organic dye;
   - low-cost semiconductor/photoanode;
   - Pt-free counter electrode;
   - electrolyte or cell component with a more environmentally friendly indication;
   - material relevant to indoor or low-light DSSC applications.

6. Manual or semi-automatic curation

   Curation is still required before ML/DFT. The reasons are:

   - material names extracted from PDFs are often noisy, for example `TiO NP 2` should be read as `TiO2 nanoparticle`;
   - performance values may contain a main value and a standard deviation in parentheses;
   - some fields are still empty and must be checked against the original paper;
   - reference dyes such as N719 should not be mixed with the main green candidate set;
   - tandem or co-sensitized DSSCs must be labeled separately.

   Curated output:

   `green_dssc_curated_for_ml_2020_2026.csv`

7. Candidate combination

   Material combinations can be generated, but they must be treated as virtual candidates, not experimental data. A PCE value from one paper must not be directly assigned to a newly generated material combination.

   Safe early-stage combinations include:

   - environmentally friendly dye + semiconductor/photoanode from the high-confidence component pool;
   - electrolyte already observed in the high-confidence dataset;
   - substrate already observed in the high-confidence dataset;
   - each combination must include source DOI information and the status `virtual_candidate_not_experimental`.

   Combination output:

   `green_dssc_virtual_combinations_2020_2026.csv`

8. Dataset for ML

   The high-confidence dataset can be used as an initial training or benchmark dataset. The main target is `pce_percent`, while initial features may include:

   - dye/material name;
   - semiconductor;
   - electrolyte;
   - substrate;
   - active area;
   - solar simulator or irradiance condition;
   - Voc, Jsc, and FF;
   - green material category;
   - publication year and paper source.

9. ML stage adapted from the reference paper

   Adaptation of the Coppola et al. workflow:

   - Model A: fast screening based on material and experimental descriptors derived from the literature-mined dataset.
   - Top candidates are selected based on high PCE, environmentally friendly material criteria, and data completeness.
   - If dye molecular structures are available as SMILES, molecular descriptors can be calculated using RDKit or Mordred.
   - Relevant ML models include XGBoost, Random Forest, Ridge, Elastic Net, KNN, and Decision Tree.

10. Follow-up DFT stage

   For the best organic dye or sensitizer candidates, DFT can be used to calculate:

   - HOMO;
   - LUMO;
   - energy gap;
   - absorption maximum;
   - oscillator strength;
   - light-harvesting efficiency;
   - alignment with the TiO2 conduction band;
   - alignment with the redox couple for dye regeneration.

11. Final candidate selection

   Final candidates are selected by combining:

   - high PCE;
   - complete and plausible Voc, Jsc, and FF values;
   - environmentally friendly material profile;
   - heavy-metal-free or lower-toxicity composition;
   - realistic synthetic feasibility;
   - compatibility with indoor or low-light DSSC operation when data are available.

## Difference From The Reference Paper

Coppola et al. focus on designing new organic dyes for indoor DSSCs using a curated literature dataset, fragment recombination, two-stage ML, and DFT.

This workflow first focuses on extracting high-confidence experimental data from 2020-2026 papers. Therefore, it represents the data-building stage before ML/DFT:

`paper -> data extraction -> high-confidence dataset -> ML screening -> DFT on top candidates -> manual/experimental validation`

## Validation Notes

The high-confidence file is stronger than broad text-mining output, but it is not yet a final public database. The `Voc`, `Jsc`, `FF`, and `PCE` values should still be manually checked for priority candidates, especially when:

- the value comes from PDF table extraction;
- the value includes a mean and standard deviation in parentheses;
- one paper reports multiple testing conditions;
- one row contains co-sensitization or tandem DSSC data.
