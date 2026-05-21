import os
import pickle
import pandas as pd
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from rdkit.ML.Descriptors import MoleculeDescriptors

# For machine learning
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score

# Get all RDKit descriptor names
DESCRIPTOR_NAMES = [desc[0] for desc in Descriptors._descList]
DESCRIPTOR_CALCULATOR = MoleculeDescriptors.MolecularDescriptorCalculator(DESCRIPTOR_NAMES)

def smiles_to_features(smiles, n_bits=1024):
    """
    Convert a SMILES string into a feature vector:
    Combines 2D RDKit descriptors and Morgan Fingerprints (ECFP4).
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
        
    # 1. RDKit Descriptors
    try:
        desc_vals = list(DESCRIPTOR_CALCULATOR.CalcDescriptors(mol))
    except Exception:
        desc_vals = [0.0] * len(DESCRIPTOR_NAMES)
        
    # 2. Morgan Fingerprints (radius=2, 1024 bits)
    try:
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=n_bits)
        fp_vals = list(fp)
    except Exception:
        fp_vals = [0] * n_bits
        
    return desc_vals + fp_vals

def load_and_preprocess_chromophore_db(csv_path):
    """Load and preprocess the chromophore database for absorption max model."""
    df = pd.read_csv(csv_path)
    # Drop rows where SMILES or target is missing
    df = df.dropna(subset=["Chromophore", "Absorption max (nm)"])
    
    # Parse target as float
    df["Absorption max (nm)"] = pd.to_numeric(df["Absorption max (nm)"], errors="coerce")
    df = df.dropna(subset=["Absorption max (nm)"])
    
    print(f"Loaded {len(df)} rows from chromophore database.")
    return df

def load_and_preprocess_dssc_db(csv_path):
    """Load and preprocess the DSSC curated database for PCE model."""
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["example_smiles", "max_pce_percent"])
    
    # Clean SMILES (sometimes they contain salt dots or mixtures, get the largest fragment)
    def clean_smiles(smiles):
        if "." in smiles:
            parts = smiles.split(".")
            parts.sort(key=len, reverse=True)
            return parts[0]
        return smiles
        
    df["SMILES_clean"] = df["example_smiles"].apply(clean_smiles)
    df["max_pce_percent"] = pd.to_numeric(df["max_pce_percent"], errors="coerce")
    df = df.dropna(subset=["max_pce_percent"])
    
    print(f"Loaded {len(df)} rows from DSSC curated database.")
    return df

def train_and_save_model(X, y, model_path, name="Model"):
    """Train a Random Forest model, evaluate, and save it to disk."""
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"Training {name} using Random Forest...")
    # Using a fast RF for responsiveness (100 estimators, max_depth 15)
    model = RandomForestRegressor(n_estimators=100, max_depth=15, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    
    # Evaluate
    preds = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)
    
    print(f"{name} Results - Test RMSE: {rmse:.4f}, R2: {r2:.4f}")
    
    # Save model
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"Saved {name} to {model_path}")
    return model

def build_and_train_pipelines():
    """Main function to train and save both ML models."""
    # 1. Train Absorption Max Model
    chrom_db_path = "data/DB for chromophore_Sci_Data_rev02.csv"
    if os.path.exists(chrom_db_path):
        df_chrom = load_and_preprocess_chromophore_db(chrom_db_path)
        # To make it fast, we can sample if it's too large, but RF can handle 20k rows easily.
        # Let's limit to first 5000 rows for extremely fast training in the sandbox, or run on full.
        # Let's train on 3000 rows to ensure fast execution and avoid CPU overload in the container.
        df_chrom_sampled = df_chrom.sample(min(3000, len(df_chrom)), random_state=42)
        
        print("Computing features for chromophore database...")
        features = []
        targets = []
        for idx, row in df_chrom_sampled.iterrows():
            feats = smiles_to_features(row["Chromophore"])
            if feats is not None:
                features.append(feats)
                targets.append(row["Absorption max (nm)"])
                
        X = np.array(features, dtype=np.float32)
        y = np.array(targets)
        
        # Clean any NaN/inf values in features (e.g. from RDKit descriptor calculation failures)
        X = np.nan_to_num(X, nan=0.0, posinf=3.4e38, neginf=-3.4e38)
        
        train_and_save_model(X, y, "data/models/model_abs_max.pkl", "Absorption Max (nm)")
    else:
        print(f"Chromophore database not found at {chrom_db_path}, skipping absorption model.")

    # 2. Train PCE Model
    dssc_db_path = "database_2018_13516220/extracted/dssc_metal_free_organic_dye_summary_curated.csv"
    if os.path.exists(dssc_db_path):
        df_dssc = load_and_preprocess_dssc_db(dssc_db_path)
        
        print("Computing features for DSSC curated database...")
        features = []
        targets = []
        for idx, row in df_dssc.iterrows():
            feats = smiles_to_features(row["SMILES_clean"])
            if feats is not None:
                features.append(feats)
                targets.append(row["max_pce_percent"])
                
        X = np.array(features, dtype=np.float32)
        y = np.array(targets)
        X = np.nan_to_num(X, nan=0.0, posinf=3.4e38, neginf=-3.4e38)
        
        train_and_save_model(X, y, "data/models/model_pce.pkl", "Experimental PCE (%)")
    else:
        print(f"DSSC database not found at {dssc_db_path}, skipping PCE model.")

if __name__ == "__main__":
    build_and_train_pipelines()
