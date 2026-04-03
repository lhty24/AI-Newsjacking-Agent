import logging
import sys

from src.config import ConfigError, validate_config
from src.pipeline import run_pipeline


def main() -> int:
    """Run the newsjacking pipeline from the command line."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        validate_config()
    except ConfigError as e:
        logging.error("%s", e)
        return 1

    run, top_variants, dist_records = run_pipeline(trigger="cli")

    if run.status == "failed":
        return 1

    if top_variants:
        # Build lookup for distribution status
        dist_by_variant = {r.variant_id: r for r in dist_records}

        print(f"\n{'=' * 60}")
        print(f"Pipeline run {run.id[:8]} — {len(top_variants)} top variant(s)")
        if run.variants_posted > 0:
            print(f"  Posted: {run.variants_posted}/{len(top_variants)}")
        print(f"{'=' * 60}")
        for i, v in enumerate(top_variants, 1):
            score_str = f"{v.score:.1f}" if v.score is not None else "N/A"
            record = dist_by_variant.get(v.id)
            status_str = f" | {record.status}" if record else ""
            print(f"\n[{i}] ({v.style}, score: {score_str}{status_str})")
            print(v.text)
            if record and record.platform_post_id:
                print(f"  → tweet: {record.platform_post_id}")
            elif record and record.error:
                print(f"  → {record.error}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
