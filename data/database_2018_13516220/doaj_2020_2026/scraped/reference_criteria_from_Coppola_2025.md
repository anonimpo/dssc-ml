# Reference Criteria Used For Green DSSC Screening

Reference paper: Carmen Coppola et al., "A combined ML and DFT strategy for the prediction of dye candidates for indoor DSSCs", npj Computational Materials 11, 28 (2025), DOI: 10.1038/s41524-025-01521-9.

Criteria adopted from the paper for this scraping pass:

- Prioritize metal-free organic sensitizers over Ru-based dyes.
- Treat D-pi-A, D-pi-A'-A, and D-A'-pi-A dye architectures as relevant for indoor DSSCs.
- Prefer materials compatible with low-cost, scalable, and sustainable DSSC fabrication.
- Keep TiO2 alignment and dye regeneration context as important DSSC constraints.
- Include natural/bio-based dyes and low-toxicity/Pt-free counter electrode materials as "green" candidates for manual curation.

Important limitation:

- The scraper is a text-mining triage tool. The `max_pce_percent_text_mined` column must be checked against the original paper table before being used as a final experimental value.
