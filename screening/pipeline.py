import os
import pickle
import pandas as pd
import numpy as np
from rdkit import Chem

from screening.generate_library import generate_library
from screening.train_ml import build_and_train_pipelines, smiles_to_features
from screening.run_xtb import run_xtb_for_smiles
from screening.run_orca import create_orca_input_file

def run_full_screening_pipeline(top_ml_count=20, check_energy_alignment=True):
    """
    Run the complete virtual screening pipeline:
    1. Generate D-pi-A virtual library.
    2. Train ML models (if not already trained).
    3. Screen and score the library using ML.
    4. Run xTB on top ML-prioritized candidates.
    5. Filter by energy level alignment.
    6. Generate ORCA inputs for the best-aligned candidates.
    """
    print("====================================================")
    print("   DSSC D-pi-A DYE SCREENING PIPELINE STARTING       ")
    print("====================================================")
    
    # 1. Virtual Library Generation
    lib_path = "data/d_pi_a_library.csv"
    if not os.path.exists(lib_path):
        print("\n[Stage 1] Virtual library not found. Generating...")
        df_lib = generate_library()
    else:
        print(f"\n[Stage 1] Loading existing virtual library from {lib_path}")
        df_lib = pd.read_csv(lib_path)
        
    print(f"Total virtual candidates in library: {len(df_lib)}")

    # 2. ML Models Check & Training
    model_abs_path = "data/models/model_abs_max.pkl"
    model_pce_path = "data/models/model_pce.pkl"
    if not os.path.exists(model_abs_path) or not os.path.exists(model_pce_path):
        print("\n[Stage 2] Machine learning models not found. Training...")
        build_and_train_pipelines()
    else:
        print("\n[Stage 2] Loading pre-trained ML models...")
        
    with open(model_abs_path, "rb") as f:
        model_abs = pickle.load(f)
    with open(model_pce_path, "rb") as f:
        model_pce = pickle.load(f)

    # 3. ML Screening
    print("\n[Stage 3] Running machine learning screening on virtual library...")
    features_list = []
    valid_indices = []
    
    for idx, row in df_lib.iterrows():
        feats = smiles_to_features(row["SMILES"])
        if feats is not None:
            features_list.append(feats)
            valid_indices.append(idx)
            
    X = np.array(features_list, dtype=np.float32)
    X = np.nan_to_num(X, nan=0.0, posinf=3.4e38, neginf=-3.4e38)
    
    # Make predictions
    abs_preds = model_abs.predict(X)
    pce_preds = model_pce.predict(X)
    
    # Map predictions back to the library DataFrame
    df_screened = df_lib.iloc[valid_indices].copy()
    df_screened["Predicted_Abs_Max_nm"] = abs_preds
    df_screened["Predicted_PCE_Percent"] = pce_preds
    
    # Rank candidates: Prioritize visible-absorbing dyes (Abs Max > 400 nm) and high PCE
    # Filter for visible-absorbing dyes first
    df_visible = df_screened[df_screened["Predicted_Abs_Max_nm"] > 400.0].copy()
    if len(df_visible) == 0:
        print("Warning: No dyes predicted to absorb above 400 nm. Using whole library.")
        df_visible = df_screened.copy()
        
    df_ranked = df_visible.sort_values(by="Predicted_PCE_Percent", ascending=False)
    
    os.makedirs("data/outputs", exist_ok=True)
    df_ranked.to_csv("data/outputs/screened_candidates_ml.csv", index=False)
    print(f"ML screening complete. Screened and ranked {len(df_ranked)} candidates.")
    print(f"Top 5 ML-predicted candidates saved to data/outputs/screened_candidates_ml.csv")
    print(df_ranked[["Donor_Name", "Pi_Name", "Acceptor_Name", "Predicted_Abs_Max_nm", "Predicted_PCE_Percent"]].head(5))

    # 4. xTB Calculations on Top Candidates
    print(f"\n[Stage 4] Performing xTB geometry optimizations on top {top_ml_count} candidates...")
    top_candidates = df_ranked.head(top_ml_count).copy()
    top_candidates["Tag"] = top_candidates.index
    
    xtb_results = []
    os.makedirs("data/xtb_runs", exist_ok=True)
    
    for count, (idx, row) in enumerate(top_candidates.iterrows()):
        smiles = row["SMILES"]
        mol_label = f"{row['Donor_Name']}-{row['Pi_Name']}-{row['Acceptor_Name']}"
        print(f"({count+1}/{top_ml_count}) Running GFN2-xTB for {mol_label}...")
        
        res = run_xtb_for_smiles(smiles, idx)
        xtb_results.append(res)
        
    df_xtb_res = pd.DataFrame(xtb_results)
    df_xtb_final = pd.concat([top_candidates.reset_index(drop=True), df_xtb_res], axis=1)
    df_xtb_final.to_csv("data/outputs/screened_candidates_xtb.csv", index=False)
    print(f"xTB calculations completed. Saved to data/outputs/screened_candidates_xtb.csv")

    # 5. Energy Alignment Check
    print("\n[Stage 5] Filtering by DSSC energy alignment constraints...")
    # DSSC energy conditions:
    # 1. LUMO > -4.0 eV (less negative, higher in energy than TiO2 CB)
    # 2. HOMO < -4.8 eV (more negative, lower in energy than I-/I3- redox potential)
    # 3. Successful xTB status
    
    df_success = df_xtb_final[df_xtb_final["xTB_Status"] == "Success"].copy()
    print(f"Successfully calculated: {len(df_success)} / {len(df_xtb_final)}")
    
    if len(df_success) > 0:
        if check_energy_alignment:
            aligned_mask = (df_success["LUMO"] > -4.0) & (df_success["HOMO"] < -4.8)
            df_aligned = df_success[aligned_mask].copy()
            print(f"Molecules satisfying energy level alignment: {len(df_aligned)}")
        else:
            df_aligned = df_success.copy()
            
        df_aligned = df_aligned.sort_values(by="Predicted_PCE_Percent", ascending=False)
        df_aligned.to_csv("data/outputs/screened_candidates_aligned.csv", index=False)
    else:
        df_aligned = pd.DataFrame()
        print("No successful xTB calculations, skipping alignment filter.")

    # 6. ORCA Input Generation for Top Aligned Candidates
    print("\n[Stage 6] Generating ORCA DFT input files for top candidates...")
    candidates_for_orca = df_aligned.head(5) if len(df_aligned) > 0 else df_success.head(5)
    
    if len(candidates_for_orca) > 0:
        os.makedirs("data/orca_inputs", exist_ok=True)
        generated_count = 0
        for idx, row in candidates_for_orca.iterrows():
            mol_id = int(row.get("Tag", idx)) # fallback index
            opt_xyz_path = f"data/xtb_runs/mol_{mol_id}_optimized.xyz"
            
            if os.path.exists(opt_xyz_path):
                # Calculate formal charge of the coupled molecule using RDKit
                smiles = row["SMILES"]
                mol = Chem.MolFromSmiles(smiles)
                charge = Chem.GetFormalCharge(mol) if mol is not None else 0
                
                mol_label = f"{row['Donor_Name']}_{row['Pi_Name']}_{row['Acceptor_Name']}"
                # 1. Geometry Optimization ORCA Input
                dest_opt_path = f"data/orca_inputs/{mol_label}_opt.inp"
                create_orca_input_file(opt_xyz_path, dest_opt_path, charge=charge, multiplicity=1, functional="B3LYP", basis="def2-SVP", task_type="Opt")
                
                # 2. TD-DFT UV-Vis ORCA Input
                dest_td_path = f"data/orca_inputs/{mol_label}_tddft.inp"
                create_orca_input_file(opt_xyz_path, dest_td_path, charge=charge, multiplicity=1, functional="CAM-B3LYP", basis="def2-SVP", task_type="TD-DFT")
                generated_count += 1
                
        print(f"Generated ORCA input files for {generated_count} molecules in data/orca_inputs/")
    else:
        print("No candidates available for ORCA input generation.")
        
    print("\n====================================================")
    print("   SCREENING PIPELINE RUN COMPLETED SUCCESSFULLY    ")
    print("====================================================")

if __name__ == "__main__":
    run_full_screening_pipeline(top_ml_count=5)
