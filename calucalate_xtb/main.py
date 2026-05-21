import pandas as pd 
from rdkit import Chem
from rdkit.Chem import AllChem
import numpy as np
from xtb.interface import Environment, Calculator, Param
from xtb.libxtb import VERBOSITY_MINIMAL

# env.set = Environment()
# env.set_verbosity(VERBOSITY_MINIMAL)
# env.set_output("error.log")

df = pd.read_csv("../DB for chromophore_Sci_Data_rev02.csv")

print(df.Chromophore)
