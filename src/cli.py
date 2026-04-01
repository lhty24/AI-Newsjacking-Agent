import logging
import sys

from src.config import LLM_API_KEY
from src.pipeline import run_pipeline


def main() -> int:
    """Run the newsjacking pipeline from the command line."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not LLM_API_KEY:
        logging.error("LLM_API_KEY environment variable is required")
        return 1

    run, top_variants = run_pipeline(trigger="cli")

    if run.status == "failed":
        return 1

    if top_variants:
        print(f"\n{'=' * 60}")
        print(f"Pipeline run {run.id[:8]} — {len(top_variants)} top variant(s)")
        print(f"{'=' * 60}")
        for i, v in enumerate(top_variants, 1):
            score_str = f"{v.score:.1f}" if v.score is not None else "N/A"
            print(f"\n[{i}] ({v.style}, score: {score_str})")
            print(v.text)
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
