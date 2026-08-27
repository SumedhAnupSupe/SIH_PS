"""Text preprocessing module for safety incident reports."""

import re
from typing import Dict, List, Tuple


class TextPreprocessor:
    """Cleans and segments raw safety incident report text."""

    def __init__(self):
        self.section_patterns = [
            (r"(?i)^#{1,3}\s+(.+)$", "heading"),
            (r"(?i)^(incident\s+(?:description|summary|details?|overview))\s*:?\s*$", "section_header"),
            (r"(?i)^(investigation\s+(?:summary|findings?|results?|details?))\s*:?\s*$", "section_header"),
            (r"(?i)^(background|cause|root\s*cause|contributing|corrective)\s*:?\s*$", "section_header"),
        ]

    def read_report(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def clean(self, raw_text: str) -> str:
        text = raw_text
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[^\x00-\x7F]+", " ", text)
        text = re.sub(r"(?i)^page\s*\d+\s*(of\s*\d+)?\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"(?i)^confidential.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"(?i)^classification:.*$", "", text, flags=re.MULTILINE)
        text = text.strip()
        return text

    def segment_sentences(self, text: str) -> List[Dict]:
        abbrevs = r"(?:Mr|Mrs|Ms|Dr|Inc|Ltd|Jr|Sr|vs|etc|approx|dept|est)\."
        pattern = rf"(?<=[.!?])\s+(?=[A-Z])"
        raw_sentences = re.split(pattern, text)
        sentences = []
        for i, sent in enumerate(raw_sentences):
            sent_clean = sent.strip()
            if not sent_clean:
                continue
            sentences.append({
                "sentence_id": i,
                "text": sent_clean,
                "is_heading": bool(re.match(r"(?i)^#{1,3}\s+", sent_clean)),
            })
        return sentences

    def segment_paragraphs(self, text: str) -> List[Dict]:
        blocks = re.split(r"\n\n+", text)
        paragraphs = []
        for i, block in enumerate(blocks):
            block_clean = block.strip()
            if not block_clean:
                continue
            paragraphs.append({
                "paragraph_id": i,
                "text": block_clean,
                "sentence_count": len(self.segment_sentences(block_clean)),
            })
        return paragraphs

    def extract_metadata(self, text: str) -> Dict[str, str]:
        metadata = {}
        patterns = {
            "incident_date": r"(?i)(?:date|incident\s*date|date\s*of\s*incident)\s*:\s*(.+?)(?:\n|$)",
            "incident_id": r"(?i)(?:incident\s*(?:id|number|no|#))\s*:\s*(.+?)(?:\n|$)",
            "location": r"(?i)(?:location|site|facility)\s*:\s*(.+?)(?:\n|$)",
            "worker_count": r"(?i)(?:number\s*of\s*(?:workers?|employees?|personnel))\s*:\s*(.+?)(?:\n|$)",
            "injury_severity": r"(?i)(?:severity|injury\s*severity|outcome)\s*:\s*(.+?)(?:\n|$)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                metadata[key] = match.group(1).strip()
        return metadata

    def preprocess(self, file_path: str) -> Dict:
        raw = self.read_report(file_path)
        cleaned = self.clean(raw)
        sentences = self.segment_sentences(cleaned)
        paragraphs = self.segment_paragraphs(cleaned)
        metadata = self.extract_metadata(cleaned)
        return {
            "raw": raw,
            "cleaned": cleaned,
            "sentences": sentences,
            "paragraphs": paragraphs,
            "metadata": metadata,
            "report_length": len(cleaned),
            "sentence_count": len(sentences),
        }
