import os
import re
import shutil
import subprocess
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem

XTB_PATH = "/home/rfa/.local/miniconda3/envs/dssc/bin/xtb"
XTB_RUNS_DIR = "data/xtb_runs"

def parse_xtb_stdout(stdout_text):
    """
    Parse xTB standard output to extract:
    - HOMO energy (eV)
    - LUMO energy (eV)
    - HOMO-LUMO Gap (eV)
    - Total Energy (Eh)
    - Dipole Moment (Debye)
    """
    homo = None
    lumo = None
    gap = None
    total_energy = None
    dipole = None
    
    # 1. HOMO / LUMO regex matching (eV)
    homo_match = re.search(r'([-\d\.]+)\s*\(HOMO\)', stdout_text)
    lumo_match = re.search(r'([-\d\.]+)\s*\(LUMO\)', stdout_text)
    if homo_match:
        homo = float(homo_match.group(1))
    if lumo_match:
        lumo = float(lumo_match.group(1))
        
    # 2. HOMO-LUMO Gap (eV)
    gap_match = re.search(r'HOMO-LUMO GAP\s+([-\d\.]+)\s*eV', stdout_text, re.IGNORECASE)
    if gap_match:
        gap = float(gap_match.group(1))
    elif homo is not None and lumo is not None:
        gap = lumo - homo
        
    # 3. Total Energy (Eh)
    energy_match = re.search(r'TOTAL ENERGY\s+([-\d\.]+)\s*Eh', stdout_text, re.IGNORECASE)
    if energy_match:
        total_energy = float(energy_match.group(1))
        
    # 4. Dipole Moment (Debye)
    # Search for the "full:" line under "molecular dipole:"
    # full:        0.004      -0.872      -0.000       2.218
    dipole_match = re.search(r'full:\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)', stdout_text)
    if dipole_match:
        dipole = float(dipole_match.group(4))
        
    return {
        "HOMO": homo,
        "LUMO": lumo,
        "Gap": gap,
        "Total_Energy": total_energy,
        "Dipole_Moment": dipole
    }

def run_xtb_for_smiles(smiles, mol_id):
    """
    Runs the full xTB geometry optimization pipeline for a SMILES string:
    1. Embed molecule in 3D using RDKit.
    2. Optimize using MMFF94.
    3. Save to XYZ file.
    4. Run xTB --opt --gfn 2.
    5. Parse and return results.
    6. Clean up temporary files.
    """
    mol_dir = os.path.join(XTB_RUNS_DIR, f"mol_{mol_id}")
    os.makedirs(mol_dir, exist_ok=True)
    
    xyz_path = os.path.join(mol_dir, f"mol_{mol_id}.xyz")
    results = {"HOMO": None, "LUMO": None, "Gap": None, "Total_Energy": None, "Dipole_Moment": None, "xTB_Status": "Failed"}
    
    try:
        # Convert SMILES to 3D Mol block
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            results["xTB_Status"] = "Invalid_SMILES"
            return results
            
        mol = Chem.AddHs(mol)
        
        # 3D structure embedding
        params = AllChem.ETKDGv3()
        params.randomSeed = 42
        embed_status = AllChem.EmbedMolecule(mol, params)
        if embed_status == -1:
            results["xTB_Status"] = "Embedding_Failed"
            return results
            
        # MMFF optimization for a reasonable starting geometry
        AllChem.MMFFOptimizeMolecule(mol)
        
        # Write to XYZ file
        Chem.MolToXYZFile(mol, xyz_path)
        
        if not os.path.exists(xyz_path):
            results["xTB_Status"] = "XYZ_Creation_Failed"
            return results
            
        # Run xTB optimization
        cmd = [XTB_PATH, f"mol_{mol_id}.xyz", "--opt", "--gfn", "2"]
        res = subprocess.run(cmd, cwd=mol_dir, capture_output=True, text=True, timeout=600)
        
        # Save output logs for traceback if needed
        with open(os.path.join(mol_dir, "xtbout.txt"), "w") as f:
            f.write(res.stdout)
            if res.stderr:
                f.write("\n=== STDERR ===\n")
                f.write(res.stderr)
                
        if res.returncode == 0:
            parsed = parse_xtb_stdout(res.stdout)
            results.update(parsed)
            results["xTB_Status"] = "Success"
            
            # Copy optimized XYZ back or keep it
            opt_xyz_src = os.path.join(mol_dir, "xtbopt.xyz")
            if os.path.exists(opt_xyz_src):
                opt_xyz_dest = os.path.join(XTB_RUNS_DIR, f"mol_{mol_id}_optimized.xyz")
                shutil.copy(opt_xyz_src, opt_xyz_dest)
        else:
            results["xTB_Status"] = f"xTB_Error_{res.returncode}"
            
    except subprocess.TimeoutExpired:
        results["xTB_Status"] = "Timeout"
    except Exception as e:
        results["xTB_Status"] = f"Python_Exception: {str(e)}"
    finally:
        # Clean up the directory to prevent cluttering the disk
        if os.path.exists(mol_dir):
            shutil.rmtree(mol_dir)
            
    return results

def run_screening_batch(csv_path, output_path, limit=10):
    """Run xTB on a batch of molecules from a CSV file."""
    df = pd.read_csv(csv_path)
    if "SMILES" not in df.columns:
        print("CSV must contain a 'SMILES' column")
        return
        
    print(f"Starting xTB calculations for up to {limit} molecules...")
    
    # Select first 'limit' rows
    sub_df = df.head(limit).copy()
    
    xtb_results = []
    for idx, row in sub_df.iterrows():
        smiles = row["SMILES"]
        print(f"Running xTB for Mol {idx}: {row.get('Donor_Name', 'Unknown')}-{row.get('Pi_Name', 'Unknown')}-{row.get('Acceptor_Name', 'Unknown')}")
        res = run_xtb_for_smiles(smiles, idx)
        xtb_results.append(res)
        print(f"  Status: {res['xTB_Status']}, HOMO: {res['HOMO']}, LUMO: {res['LUMO']}, Gap: {res['Gap']}")
        
    res_df = pd.DataFrame(xtb_results)
    final_df = pd.concat([sub_df.reset_index(drop=True), res_df], axis=1)
    final_df.to_csv(output_path, index=False)
    print(f"Batch calculations finished. Results saved to {output_path}")

if __name__ == "__main__":
    # Test batch run on first 2 molecules of the generated library
    os.makedirs(XTB_RUNS_DIR, exist_ok=True)
    run_screening_batch("data/d_pi_a_library.csv", "data/d_pi_a_library_xtb_test.csv", limit=2)
