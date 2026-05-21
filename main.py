import argparse
import sys
import os

# Ensure the project root is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from screening.generate_library import generate_library
from screening.train_ml import build_and_train_pipelines
from screening.pipeline import run_full_screening_pipeline

def main():
    parser = argparse.ArgumentParser(description="DSSC D-pi-A Natural-Inspired Dye Screening Pipeline")
    parser.add_argument("--generate", action="store_true", help="Generate the D-pi-A combinatorial virtual library")
    parser.add_argument("--train", action="store_true", help="Train ML models for absorption max and experimental PCE")
    parser.add_argument("--pipeline", action="store_true", help="Execute full pipeline: generate, ML screen, xTB, and ORCA input generation")
    parser.add_argument("--top-ml", type=int, default=10, help="Number of top ML-prioritized candidates to pass to xTB (default: 10)")
    parser.add_argument("--no-energy-filter", action="store_true", help="Disable the xTB HOMO/LUMO band-alignment filter for ORCA generation")
    
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
        
    if args.generate:
        print("\n--- Starting Library Generation ---")
        generate_library()
        
    if args.train:
        print("\n--- Starting Model Training ---")
        build_and_train_pipelines()
        
    if args.pipeline:
        print("\n--- Starting Full Screening Pipeline ---")
        run_full_screening_pipeline(top_ml_count=args.top_ml, check_energy_alignment=not args.no_energy_filter)

if __name__ == "__main__":
    main()
