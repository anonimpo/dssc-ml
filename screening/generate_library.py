import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem

# Define natural Donor fragments (must have exactly one [At] atom)
DONORS = {
    # Natural-derived Donors
    "Coumarin": "O=C1Oc2ccc([At])cc2C=C1",
    "Coumarin_dimethylamino": "O=C1Oc2ccc([At])c(N(C)C)c2C=C1",
    "Pelargonidin_inspired": "Oc1ccc(-c2[o+]c3cc(O)cc(O)c3cc2[At])cc1",
    "Cyanidin_inspired": "Oc1ccc(O)c(-c2[o+]c3cc(O)cc(O)c3cc2[At])c1",
    "Delphinidin_inspired": "Oc1c(O)c(O)cc(-c2[o+]c3cc(O)cc(O)c3cc2[At])c1",
    "Peonidin_inspired": "COc1cc(-c2[o+]c3cc(O)cc(O)c3cc2[At])ccc1O",
    "Malvidin_inspired": "COc1cc(-c2[o+]c3cc(O)cc(O)c3cc2[At])cc(OC)c1O",
    "Petunidin_inspired": "Oc1c(O)c(OC)cc(-c2[o+]c3cc(O)cc(O)c3cc2[At])c1",
    "Quercetin_inspired": "O=c1c(O)c(-c2ccc(O)c(O)c2)oc2cc(O)c([At])cc21",
    "Apigenin_inspired": "O=c1cc(-c2ccc(O)cc2)oc2cc(O)c([At])cc21",
    "Luteolin_inspired": "O=c1cc(-c2ccc(O)c(O)c2)oc2cc(O)c([At])cc21",
    "Kaempferol_inspired": "O=c1c(O)c(-c2ccc(O)cc2)oc2cc(O)c([At])cc21",
    "Myricetin_inspired": "O=c1c(O)c(-c2cc(O)c(O)c(O)c2)oc2cc(O)c([At])cc21",
    "Chrysin_inspired": "O=c1cc(-c2ccccc2)oc2cc(O)c([At])cc21",
    "Genistein_inspired": "O=c1c(-c2ccc(O)cc2)coc2cc(O)c([At])cc21",
    "Lawsone_inspired": "O=C1c2ccccc2C(=O)C(O)=C1[At]",
    "Plumbagin_inspired": "CC1=C([At])C(=O)c2cccc(O)c2C1=O",
    "Alizarin_inspired": "O=C1c2ccccc2C(=O)c3c([At])c(O)c(O)cc31",
    "Purpurin_inspired": "O=C1c2ccccc2C(=O)c3c([At])c(O)c(O)c(O)c31",
    "Curcumin_inspired": "COc1cc(/C=C/C(=O)/C=C/c2cc(OC)c(O)cc2[At])ccc1O",
    "Demethoxycurcumin_inspired": "Oc1ccc(/C=C/C(=O)/C=C/c2cc(OC)c(O)cc2[At])cc1",
    "Bisdemethoxycurcumin_inspired": "O=C(/C=C/c1ccc(O)cc1)/C=C/c2ccc(O)c([At])c2"
}

# Define Pi-linkers (must have exactly one [I] and one [Br] atom)
PI_LINKERS = {
    "Thiophene": "[I]c1ccsc1[Br]",
    "Benzene": "[I]c1ccc([Br])cc1",
    "Furan": "[I]c1ccoc1[Br]",
    "Thienothiophene": "[I]c1cc2c(s1)scc2[Br]",
    "Ethyne": "[I]C#C[Br]",
    "Ethene": "[I]/C=C/[Br]",
    "Benzothiadiazole": "[I]c1ccc2nsnc2c1[Br]",
    "Bithiophene": "[I]c1ccsc1-c2cc([Br])cs2",
    "Pyrrole_N-methyl": "[I]c1ccn(C)c1[Br]"
}

# Define Acceptors (must have exactly one [Cl] atom)
ACCEPTORS = {
    "Cyanoacrylic_acid": "[Cl]C=C(C#N)C(=O)O",
    "Acrylic_acid": "[Cl]C=CC(=O)O",
    "Benzoic_acid": "[Cl]c1ccc(C(=O)O)cc1",
    "Rhodanine-3-acetic_acid": "O=C1S/C(=C\\[Cl])/C(=O)N1CC(=O)O",
    "Phosphonic_acid": "[Cl]C=CP(=O)(O)O",
    "Barbituric_acid": "O=C1NC(=O)NC(=O)/C1=C/[Cl]"
}

def build_d_pi_a(donor_smiles, pi_smiles, acceptor_smiles):
    """
    Connect Donor, Pi-linker, and Acceptor fragments.
    1. Donor-[At] + [I]-pi-[Br] -> Donor-pi-[Br]
    2. Donor-pi-[Br] + [Cl]-Acceptor -> Donor-pi-Acceptor
    """
    d_mol = Chem.MolFromSmiles(donor_smiles)
    pi_mol = Chem.MolFromSmiles(pi_smiles)
    a_mol = Chem.MolFromSmiles(acceptor_smiles)
    
    if d_mol is None or pi_mol is None or a_mol is None:
        return None
        
    # Step 1: Couple Donor and Pi-linker
    rxn1 = AllChem.ReactionFromSmarts('[*:1]-[At].[I]-[*:2] >> [*:1]-[*:2]')
    products1 = rxn1.RunReactants((d_mol, pi_mol))
    if not products1 or not products1[0]:
        return None
    intermediate = products1[0][0]
    
    # Step 2: Couple Intermediate and Acceptor
    rxn2 = AllChem.ReactionFromSmarts('[*:1]-[Br].[Cl]-[*:2] >> [*:1]-[*:2]')
    products2 = rxn2.RunReactants((intermediate, a_mol))
    if not products2 or not products2[0]:
        return None
    final_mol = products2[0][0]
    
    # Sanitize and return SMILES
    try:
        Chem.SanitizeMol(final_mol)
        return Chem.MolToSmiles(final_mol)
    except Exception:
        return None

def generate_library():
    """Generate the combinatorial D-pi-A library and save to CSV."""
    rows = []
    
    for d_name, d_smiles in DONORS.items():
        for pi_name, pi_smiles in PI_LINKERS.items():
            for a_name, a_smiles in ACCEPTORS.items():
                smiles = build_d_pi_a(d_smiles, pi_smiles, a_smiles)
                if smiles:
                    # Clean up SMILES structure (remove stereochemistry tags for general screening)
                    mol = Chem.MolFromSmiles(smiles)
                    if mol:
                        # Find anchoring group type
                        anchor_type = "None"
                        cooh_pat = Chem.MolFromSmarts("[CX3](=O)[OX2H,OX1H0-]")
                        cn_pat = Chem.MolFromSmarts("[NX1]#C")
                        po3_pat = Chem.MolFromSmarts("P(=O)(O)O")
                        
                        if mol.HasSubstructMatch(po3_pat):
                            anchor_type = "phosphonic_acid"
                        elif mol.HasSubstructMatch(cooh_pat):
                            if mol.HasSubstructMatch(cn_pat):
                                anchor_type = "cyanoacrylate"
                            else:
                                anchor_type = "carboxylic_acid"
                            
                        # Natural or Synthetic source
                        source = "Synthetic" if d_name in ["Triphenylamine", "Carbazole", "Phenothiazine", "Indoline"] else "Natural-derived"
                        
                        rows.append({
                            "Donor_Name": d_name,
                            "Pi_Name": pi_name,
                            "Acceptor_Name": a_name,
                            "Donor_SMILES": d_smiles,
                            "Pi_SMILES": pi_smiles,
                            "Acceptor_SMILES": a_smiles,
                            "SMILES": Chem.MolToSmiles(mol, isomericSmiles=False),
                            "Source_Class": source,
                            "Anchoring_Group": anchor_type
                        })
                        
    df = pd.DataFrame(rows)
    # Deduplicate by SMILES
    df = df.drop_duplicates(subset=["SMILES"])
    df.to_csv("data/d_pi_a_library.csv", index=False)
    print(f"Generated {len(df)} unique D-pi-A dye candidates. Saved to data/d_pi_a_library.csv")
    return df

if __name__ == "__main__":
    generate_library()
