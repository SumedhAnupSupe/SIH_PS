"""NLP Pipeline Service - wraps the UPDATED SIF NLP pipeline + attention model."""

import json
import tempfile
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.services.ingest_service import ingest_report
from app.db import engine


class NLPService:
    """Service to run the SIF NLP pipeline + attention model on raw report text."""
    
    def __init__(self):
        self._nlp_pipeline = None
        self._attention_pipeline = None
    
    def _get_nlp_pipeline(self):
        """Lazy-load the NLP pipeline."""
        if self._nlp_pipeline is None:
            import sys
            pipeline_path = Path(__file__).resolve().parent.parent.parent.parent / "models" / "sif_nlp_pipeline"
            if str(pipeline_path) not in sys.path:
                sys.path.insert(0, str(pipeline_path))
            from sif_nlp.pipeline import SIFPipeline
            self._nlp_pipeline = SIFPipeline(output_dir=str(pipeline_path / "outputs"))
        return self._nlp_pipeline
    
    def _get_attention_pipeline(self):
        """Lazy-load the attention model."""
        if self._attention_pipeline is None:
            import sys
            pipeline_path = Path(__file__).resolve().parent.parent.parent.parent / "models" / "sif_attention_model"
            nlp_outputs = str(Path(__file__).resolve().parent.parent.parent.parent / "models" / "sif_nlp_pipeline" / "outputs")
            if str(pipeline_path) not in sys.path:
                sys.path.insert(0, str(pipeline_path))
            from sif_attention.pipeline import AttentionPipeline
            self._attention_pipeline = AttentionPipeline(
                upstream_output_dir=nlp_outputs,
                downstream_output_dir=str(pipeline_path / "outputs"),
                load_trained_models=False,
            )
        return self._attention_pipeline
    
    def analyze_report_text(
        self,
        raw_text: str,
        incident_id: Optional[str] = None,
        date: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Tuple[Dict, str, Optional[Dict]]:
        """
        Analyze a raw report text and return the analysis + summary + attention assessment.
        
        Returns:
            Tuple of (analysis_dict, summary_text, attention_output_or_None)
        """
        # Create a temporary file with the report text
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            metadata_lines = []
            if incident_id:
                metadata_lines.append(f"Incident ID: {incident_id}")
            if date:
                metadata_lines.append(f"Incident Date: {date}")
            if location:
                metadata_lines.append(f"Location: {location}")
            if metadata_lines:
                f.write("\n".join(metadata_lines) + "\n\n")
            f.write(raw_text)
            temp_path = f.name
        
        try:
            # Run NLP pipeline
            nlp_pipeline = self._get_nlp_pipeline()
            results = nlp_pipeline.run(temp_path)
            
            if not results:
                raise ValueError("Pipeline returned no results")
            
            result = results[0]
            analysis = result["analysis"]
            summary = result["summary"]
            
            # Override incident_id if provided
            if incident_id:
                analysis["incident_id"] = incident_id
                analysis.setdefault("metadata", {})["incident_id"] = incident_id
            
            # Run attention model
            attention_output = None
            try:
                attention_pipeline = self._get_attention_pipeline()
                single_id = analysis.get("incident_id", incident_id)
                if single_id:
                    prediction = attention_pipeline.run_single(single_id)
                    attention_output = prediction.to_assessment_json()
            except Exception as e:
                print(f"WARNING: Attention model failed: {e}")
            
            return analysis, summary, attention_output
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
    
    def ingest_analysis(
        self, analysis: Dict, raw_text: str = "",
        summary: str = "", attention_output: Optional[Dict] = None
    ) -> int:
        """Ingest an analysis into the database."""
        with engine.begin() as conn:
            rid = ingest_report(conn, analysis, {}, raw_text, summary, attention_output=attention_output)
            return rid
    
    def analyze_and_ingest(
        self,
        raw_text: str,
        incident_id: Optional[str] = None,
        date: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Dict:
        """Analyze a report and ingest it in one call."""
        analysis, summary, attention_output = self.analyze_report_text(
            raw_text, incident_id, date, location
        )
        rid = self.ingest_analysis(analysis, raw_text, summary, attention_output)
        
        return {
            "report_id": rid,
            "incident_id": incident_id or analysis.get("incident_id"),
            "analysis": analysis,
            "summary": summary,
            "sif_score": analysis.get("sif_score", {}),
            "life_saving_rules": analysis.get("life_saving_rules", {}),
            "attention": attention_output,
        }


# Singleton instance
nlp_service = NLPService()
