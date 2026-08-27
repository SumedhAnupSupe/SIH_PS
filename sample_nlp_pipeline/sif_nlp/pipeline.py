"""Main pipeline module - orchestrates the SIF NLP processing pipeline."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .preprocessor import TextPreprocessor
from .evidence_extractor import EvidenceExtractor
from .precursor_mapper import PrecursorMapper
from .feature_engineer import FeatureEngineer
from .summarizer import SIFSummarizer
from .sif_scorer import compute_sif_score
from .lsr_extractor import extract_life_saving_rules


class SIFPipeline:
    """End-to-end SIF NLP pipeline: raw report -> evidence -> features -> DataFrame."""

    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "analyses").mkdir(exist_ok=True)
        (self.output_dir / "summaries").mkdir(exist_ok=True)
        self.preprocessor = TextPreprocessor()
        self.evidence_extractor = EvidenceExtractor()
        self.precursor_mapper = PrecursorMapper()
        self.feature_engineer = FeatureEngineer()
        self.summarizer = SIFSummarizer()

    def _extract_incident_id(self, file_path: str, preprocessed: Dict) -> str:
        metadata = preprocessed.get("metadata", {})
        if "incident_id" in metadata:
            return metadata["incident_id"]
        basename = Path(file_path).stem
        return basename

    def process_single(self, file_path: str) -> Dict:
        preprocessed = self.preprocessor.preprocess(file_path)
        incident_id = self._extract_incident_id(file_path, preprocessed)
        extracted = self.evidence_extractor.extract_all(preprocessed)
        mapped = self.precursor_mapper.map_precursors(extracted)
        df = self.feature_engineer.build_features(
            incident_id, preprocessed, extracted, mapped
        )
        validation_errors = self.feature_engineer.validate(df)
        if validation_errors:
            print(f"WARNING: Validation errors for {incident_id}:")
            for err in validation_errors:
                print(f"  - {err}")
        
        # Compute SIF score from mapped precursors
        sif_score = compute_sif_score(mapped)
        
        # Extract Life-Saving Rules
        lsr_analysis = extract_life_saving_rules(preprocessed, extracted)
        
        summary = self.summarizer.generate_summary(
            incident_id, preprocessed, extracted, mapped, lsr_analysis
        )
        analysis = self.summarizer.generate_analysis_json(
            incident_id, preprocessed, extracted, mapped, summary, sif_score, lsr_analysis
        )
        return {
            "incident_id": incident_id,
            "preprocessed": preprocessed,
            "extracted_evidence": extracted,
            "mapped_precursors": mapped,
            "dataframe": df,
            "summary": summary,
            "analysis": analysis,
            "validation_errors": validation_errors,
            "sif_score": sif_score,
            "lsr_analysis": lsr_analysis,
        }

    def _save_single(self, result: Dict) -> None:
        incident_id = result["incident_id"]
        cleaned_path = self.output_dir / f"report_cleaned_{incident_id}.txt"
        with open(cleaned_path, "w", encoding="utf-8") as f:
            f.write(result["preprocessed"]["cleaned"])
        summary_path = self.output_dir / "summaries" / f"{incident_id}.txt"
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(result["summary"])
        analysis_path = self.output_dir / "analyses" / f"{incident_id}.json"
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(result["analysis"], f, indent=2, default=str)
        print(f"  Saved: {cleaned_path.name}, {summary_path.name}, {analysis_path.name}")

    def _save_combined(self, all_results: List[Dict]) -> None:
        if not all_results:
            print("No results to save.")
            return
        dfs = [r["dataframe"] for r in all_results]
        combined_df = pd.concat(dfs, ignore_index=True)
        combined_raw = self.feature_engineer.build_raw_features(combined_df)
        encoded_path = self.output_dir / "sif_features_encoded.csv"
        combined_df.to_csv(encoded_path, index=False)
        print(f"  Saved encoded DataFrame: {encoded_path}")
        raw_path = self.output_dir / "sif_features_raw.csv"
        combined_raw.to_csv(raw_path, index=False)
        print(f"  Saved raw DataFrame: {raw_path}")
        try:
            parquet_path = self.output_dir / "sif_features.parquet"
            combined_df.to_parquet(parquet_path, index=False)
            print(f"  Saved parquet: {parquet_path}")
        except Exception as e:
            print(f"  Could not save parquet (install pyarrow): {e}")

    def run(self, input_path: str) -> List[Dict]:
        input_path_obj = Path(input_path)
        all_results = []
        if input_path_obj.is_file():
            print(f"Processing single report: {input_path}")
            result = self.process_single(input_path)
            self._save_single(result)
            all_results.append(result)
            print(f"\nSummary for {result['incident_id']}:")
            print(result["summary"])
        elif input_path_obj.is_dir():
            txt_files = sorted(input_path_obj.glob("*.txt"))
            if not txt_files:
                print(f"No .txt files found in {input_path}")
                return all_results
            print(f"Processing {len(txt_files)} reports from {input_path}")
            for i, txt_file in enumerate(txt_files, 1):
                print(f"\n[{i}/{len(txt_files)}] Processing: {txt_file.name}")
                try:
                    result = self.process_single(str(txt_file))
                    self._save_single(result)
                    all_results.append(result)
                    print(f"  Precursors PRESENT: {sum(1 for p in result['mapped_precursors'].values() if p['status'] == 3)}/13")
                except Exception as e:
                    print(f"  ERROR processing {txt_file.name}: {e}")
        else:
            print(f"Input path does not exist: {input_path}")
            return all_results
        if all_results:
            self._save_combined(all_results)
            print(f"\nPipeline complete. Processed {len(all_results)} report(s).")
            print(f"Output directory: {self.output_dir}")
        return all_results

    def run_and_return_dataframes(self, input_path: str) -> pd.DataFrame:
        self.run(input_path)
        encoded_path = self.output_dir / "sif_features_encoded.csv"
        if encoded_path.exists():
            return pd.read_csv(encoded_path)
        return pd.DataFrame()
