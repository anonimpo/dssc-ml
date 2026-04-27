# Alur Dataset High-Confidence DSSC Ramah Lingkungan

Rujukan utama: Coppola et al., "A combined ML and DFT strategy for the prediction of dye candidates for indoor DSSCs", npj Computational Materials 11, 28 (2025), DOI: 10.1038/s41524-025-01521-9.

## Tujuan

Membangun dataset DSSC ramah lingkungan dari paper 2020-2026 dengan tingkat kepercayaan tinggi, lalu menyiapkannya untuk tahap machine learning dan DFT seperti pendekatan pada paper rujukan.

Dataset utama yang dipakai:

`green_dssc_high_confidence_records_2020_2026.csv`

## Alur Kerja

1. Literature mining

   Sumber paper diambil dari DOAJ 2020-2026 dengan kata kunci DSSC, natural dye, green synthesis, metal-free organic dye, bio-based dye, Pt-free counter electrode, dan dye-sensitized solar cell.

2. Full-text scraping

   Metadata, HTML, dan PDF paper disimpan di folder `doaj_2020_2026/scraped/raw/`. Tahap ini hanya mengumpulkan kandidat sumber, belum dianggap sebagai data final.

3. Ekstraksi field DSSC

   Field yang dicari mengikuti ChemDataExtractor photovoltaic/DSSC:

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

   Record hanya dimasukkan ke file utama jika memenuhi kriteria kuat:

   - berasal dari tabel HTML, tabel PDF, atau kalimat yang memuat properti inti lengkap;
   - memiliki semua properti inti: Voc, Jsc, FF, dan PCE;
   - memiliki DOI atau sumber paper yang jelas;
   - masih diberi status `needs_manual_validation` agar nilai final tetap bisa dicek ke paper asli.

5. Green/material relevance screening

   Kandidat diprioritaskan jika termasuk salah satu kategori berikut:

   - natural or bio-based dye;
   - metal-free organic dye;
   - low-cost semiconductor/photoanode;
   - Pt-free counter electrode;
   - electrolyte atau komponen sel dengan indikasi lebih ramah lingkungan;
   - material yang relevan untuk DSSC indoor atau low-light.

6. Kurasi manual/semiautomatis

   Kurasi tetap diperlukan sebelum ML/DFT. Alasannya:

   - nama material dari PDF sering tidak rapi, misalnya `TiO NP 2` perlu dibaca sebagai `TiO2 nanoparticle`;
   - nilai performa kadang berisi nilai utama dan standar deviasi dalam tanda kurung;
   - beberapa field masih kosong dan harus dicek ke paper asli;
   - kandidat reference dye seperti N719 tidak boleh dicampur dengan kandidat green utama;
   - tandem/co-sensitized DSSC harus diberi label terpisah.

   Output kurasi:

   `green_dssc_curated_for_ml_2020_2026.csv`

7. Kombinasi kandidat

   Kombinasi boleh dilakukan, tetapi harus diperlakukan sebagai kandidat virtual, bukan data eksperimen. Nilai PCE dari satu paper tidak boleh langsung ditempel ke kombinasi material baru.

   Kombinasi yang aman untuk tahap awal:

   - dye ramah lingkungan + semiconductor/photoanode dari pool high-confidence;
   - electrolyte yang sudah dikenal dari data high-confidence;
   - substrate yang sudah muncul di data high-confidence;
   - setiap kombinasi diberi sumber DOI dan status `virtual_candidate_not_experimental`.

   Output kombinasi:

   `green_dssc_virtual_combinations_2020_2026.csv`

8. Dataset untuk ML

   Dataset high-confidence dapat dipakai sebagai training/benchmark awal. Target utama adalah `pce_percent`, sedangkan fitur awal dapat mencakup:

   - dye/material name;
   - semiconductor;
   - electrolyte;
   - substrate;
   - active area;
   - solar simulator atau irradiance condition;
   - Voc, Jsc, FF;
   - kategori green material;
   - tahun dan sumber paper.

9. Tahap ML mirip paper rujukan

   Adaptasi dari paper Coppola et al.:

   - Model A: screening cepat berbasis descriptor material/eksperimental yang bisa dibuat dari dataset literature-mined.
   - Kandidat terbaik dipilih berdasarkan PCE tinggi, material ramah lingkungan, dan data lengkap.
   - Jika struktur molekul dye tersedia dalam bentuk SMILES, descriptor molekul dapat dihitung dengan RDKit/Mordred.
   - Model ML yang relevan: XGBoost, Random Forest, Ridge, Elastic Net, KNN, atau Decision Tree.

10. Tahap DFT lanjutan

   Untuk dye organik atau kandidat sensitizer terbaik, tahap DFT dapat menghitung:

   - HOMO;
   - LUMO;
   - energy gap;
   - absorption maximum;
   - oscillator strength;
   - light-harvesting efficiency;
   - alignment dengan TiO2 conduction band;
   - alignment dengan redox couple untuk dye regeneration.

11. Seleksi kandidat final

   Kandidat final dipilih dari kombinasi:

   - PCE tinggi;
   - Voc, Jsc, FF lengkap dan masuk akal;
   - material ramah lingkungan;
   - bebas logam berat atau lebih rendah toksisitasnya;
   - kandidat sintetis masih realistis;
   - kompatibel dengan DSSC indoor/low-light bila data tersedia.

## Perbedaan Dengan Paper Rujukan

Paper Coppola et al. fokus pada desain dye organik baru untuk indoor DSSC dengan dataset literatur terkurasi, fragment recombination, ML dua tahap, dan DFT.

Workflow ini fokus lebih dulu pada ekstraksi data eksperimental high-confidence dari paper 2020-2026. Jadi posisinya adalah tahap awal sebelum ML/DFT:

`paper -> ekstraksi data -> high-confidence dataset -> ML screening -> DFT kandidat terbaik -> validasi manual/eksperimental`

## Catatan Validasi

File high-confidence sudah lebih kuat daripada hasil text-mining biasa, tetapi belum final sebagai database publik. Nilai `Voc`, `Jsc`, `FF`, dan `PCE` tetap perlu dicek manual untuk kandidat prioritas, terutama jika:

- nilai berasal dari PDF table extraction;
- nilai mengandung rata-rata dan standar deviasi dalam tanda kurung;
- satu paper melaporkan kondisi pengujian berbeda;
- satu baris mengandung co-sensitization atau tandem DSSC.
