"""SIF NLP Pipeline - Evidence-to-Feature Transformation System."""

from .config import SIF_PRECURSORS, PRECURSOR_ENCODING, DATAFRAME_SCHEMA
from .preprocessor import TextPreprocessor
from .evidence_extractor import EvidenceExtractor
from .precursor_mapper import PrecursorMapper
from .feature_engineer import FeatureEngineer
from .summarizer import SIFSummarizer
from .pipeline import SIFPipeline

__all__ = [
    "SIF_PRECURSORS",
    "PRECURSOR_ENCODING",
    "DATAFRAME_SCHEMA",
    "TextPreprocessor",
    "EvidenceExtractor",
    "PrecursorMapper",
    "FeatureEngineer",
    "SIFSummarizer",
    "SIFPipeline",
]
