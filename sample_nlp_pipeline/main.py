#!/usr/bin/env python3
"""Main entry point for the SIF NLP Pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sif_nlp.pipeline import SIFPipeline


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <input_path>")
        print("  input_path: path to a .txt report file or directory of reports")
        print("")
        print("Examples:")
        print("  python main.py reports/report_001.txt")
        print("  python main.py reports/")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = "outputs"
    if len(sys.argv) >= 3:
        output_dir = sys.argv[2]

    pipeline = SIFPipeline(output_dir=output_dir)
    results = pipeline.run(input_path)

    if results:
        print(f"\n{'='*60}")
        print("PIPELINE RESULTS SUMMARY")
        print(f"{'='*60}")
        for r in results:
            print(f"\nIncident: {r['incident_id']}")
            print(f"Validation: {'PASS' if not r['validation_errors'] else 'FAIL'}")
            if r['validation_errors']:
                for e in r['validation_errors']:
                    print(f"  - {e}")


if __name__ == "__main__":
    main()
