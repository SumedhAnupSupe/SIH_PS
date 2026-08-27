#!/usr/bin/env python3
"""CLI entry point for the SIF Attention Prioritization Model.

Usage:
    # Process all incidents from upstream outputs (rule-based cold start)
    python main.py /path/to/upstream/outputs/

    # Process a single incident
    python main.py /path/to/upstream/outputs/ --incident INC-2026-001

    # Process with custom output directory
    python main.py /path/to/upstream/outputs/ --output-dir my_outputs/

    # Train models (requires labeled data)
    python main.py /path/to/upstream/outputs/ --train \
        --labels-csv /path/to/labels.csv

    # Process with pre-trained models
    python main.py /path/to/upstream/outputs/ --models-dir models/
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SIF Attention Prioritization Downstream Model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "upstream_dir",
        help="Path to the upstream NLP pipeline output directory",
    )
    parser.add_argument(
        "--incident", "-i",
        help="Process a single incident by ID",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="outputs",
        help="Output directory (default: outputs)",
    )
    parser.add_argument(
        "--models-dir", "-m",
        default="models",
        help="Models directory (default: models)",
    )
    parser.add_argument(
        "--train", "-t",
        action="store_true",
        help="Train models using labeled data",
    )
    parser.add_argument(
        "--labels-csv",
        help="Path to labeled training data CSV (required with --train)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger("main")

    # Import here to allow --help without dependencies
    from sif_attention.pipeline import AttentionPipeline
    from sif_attention.trainer import AttentionModelTrainer

    upstream_dir = Path(args.upstream_dir)
    if not upstream_dir.exists():
        logger.error("Upstream directory not found: %s", upstream_dir)
        return 1

    if args.train:
        return _run_training(upstream_dir, args)

    # --- Inference mode ---
    pipeline = AttentionPipeline(
        upstream_output_dir=str(upstream_dir),
        downstream_output_dir=args.output_dir,
        models_dir=args.models_dir,
    )

    if args.incident:
        try:
            pred = pipeline.run_single(args.incident)
            print("\n" + "=" * 60)
            print(f"Assessment for {args.incident}")
            print("=" * 60)
            from sif_attention.output_generator import OutputGenerator
            og = OutputGenerator(args.output_dir)
            print(og._render_summary(pred))
        except ValueError as e:
            logger.error(str(e))
            return 1
    else:
        result = pipeline.run()
        predictions = result["predictions"]
        dashboard = result["dashboard"]

        print("\n" + "=" * 60)
        print("SIF ATTENTION ASSESSMENT -- BATCH RESULTS")
        print("=" * 60)
        print(f"Processed: {len(predictions)} incidents")
        print(f"Output dir: {result['output_dir']}")
        print(f"Prediction CSV: {result['prediction_csv']}")
        print()

        if dashboard:
            print("Dashboard Summary:")
            print(f"  Attention Distribution: {dashboard.get('attention_distribution', {})}")
            print(f"  Systemic Distribution: {dashboard.get('systemic_distribution', {})}")
            print(f"  Human Review Required: {dashboard.get('human_review_required_count', 0)}")
            print(f"  Average Urgency Score: {dashboard.get('average_urgency_score', 0):.2f}")
            print(f"  Average Risk Potential: {dashboard.get('average_risk_potential', 0):.2f}")
            print()
            print("Top Actions:")
            for action, count in dashboard.get("top_actions", {}).items():
                print(f"  {action}: {count}")
            print()
            print("Top Drivers:")
            for driver, count in dashboard.get("top_drivers", {}).items():
                print(f"  {driver}: {count}")

    return 0


def _run_training(upstream_dir: Path, args) -> int:
    """Run model training with labeled data."""
    logger = logging.getLogger("main.train")

    if not args.labels_csv:
        logger.error("--labels-csv is required for training")
        return 1

    labels_path = Path(args.labels_csv)
    if not labels_path.exists():
        logger.error("Labels CSV not found: %s", labels_path)
        return 1

    from sif_attention.input_loader import InputLoader
    from sif_attention.feature_engineer import AttentionFeatureEngineer
    from sif_attention.trainer import AttentionModelTrainer
    from sif_attention.config import ACTION_LABELS, SYSTEMIC_ORDER

    # Load upstream features
    loader = InputLoader(str(upstream_dir))
    inputs = loader.load_all()

    # Build features
    fe = AttentionFeatureEngineer()
    feature_df = fe.build_dataframe(inputs)

    # Load labels
    labels_df = pd.read_csv(labels_path)
    logger.info("Loaded %d labels", len(labels_df))

    # Align features and labels
    merged = feature_df.merge(labels_df, on="incident_id", how="inner")
    feature_cols = [c for c in feature_df.columns if c != "incident_id"]
    X = merged[feature_cols].values.astype(float)

    # Urgency labels
    y_urgency = merged["urgency_label"].values

    # Action labels (binary columns)
    action_cols = [f"action_{a.lower()}" for a in ACTION_LABELS if f"action_{a.lower()}" in merged.columns]
    y_actions = merged[action_cols].values if action_cols else np.zeros((len(merged), len(ACTION_LABELS)))

    # Systemic labels
    y_systemic = merged["systemic_attention_label"].values if "systemic_attention_label" in merged.columns else np.array(["NONE"] * len(merged))

    # Train
    trainer = AttentionModelTrainer(output_dir=args.models_dir)
    results = trainer.train_all(X, y_urgency, y_actions, y_systemic, feature_cols)
    trainer.save_models()

    # Print results
    print("\nTraining Results:")
    print(json.dumps(results, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
