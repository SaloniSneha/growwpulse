"""
CLI Entry Point for Groww Weekly Review Pulse
Usage: python -m groww_pulse.main --phase all --weeks 10 --send
"""

import argparse
import logging
import sys
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("groww_pulse.main")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Groww Weekly Review Pulse — pipeline runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m groww_pulse.main --phase all --weeks 10
  python -m groww_pulse.main --phase scrape --weeks 8
  python -m groww_pulse.main --phase all --send --recipient you@example.com
  python -m groww_pulse.main --phase report --date 2025-01-27
        """,
    )
    parser.add_argument(
        "--phase",
        choices=["scrape", "analyze", "classify", "report", "email", "all"],
        default="all",
        help="Which phase to run (default: all)",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=10,
        choices=range(8, 13),
        metavar="{8-12}",
        help="Review window in weeks (default: 10)",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=5000,
        help="Max reviews to fetch (default: 5000)",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send email via SMTP (default: dry-run only)",
    )
    parser.add_argument(
        "--recipient",
        type=str,
        help="Email recipient address",
    )
    parser.add_argument(
        "--recipient-name",
        type=str,
        help="Recipient first name for personalised greeting",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Report date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock review data instead of scraping (for testing)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    report_date = args.date or datetime.now(timezone.utc).date().isoformat()

    logger.info(f"╔══════════════════════════════════════════════════")
    logger.info(f"║  Groww Weekly Review Pulse")
    logger.info(f"║  Phase: {args.phase} | Weeks: {args.weeks} | Date: {report_date}")
    logger.info(f"╚══════════════════════════════════════════════════")

    try:
        reviews_path = None
        themes = None
        grouped_path = None
        md_path = None

        # ── Phase 1: Scrape ────────────────────────────────────────────────
        if args.phase in ("scrape", "all"):
            from groww_pulse.phase1 import run_phase1
            reviews_path = run_phase1(
                weeks=args.weeks,
                max_reviews=args.max_reviews,
                use_mock=args.mock,
            )

        # ── Phase 2a: Theme Discovery ──────────────────────────────────────
        if args.phase in ("analyze", "all"):
            from groww_pulse.phase2 import run_phase2a
            themes = run_phase2a(reviews_path=reviews_path)

        # ── Phase 2b: Classification ───────────────────────────────────────
        if args.phase in ("classify", "all"):
            from groww_pulse.phase2 import run_phase2b
            if themes is None:
                # Rerun 2a to get themes
                from groww_pulse.phase2 import run_phase2a
                themes = run_phase2a(reviews_path=reviews_path)
            grouped_path = run_phase2b(themes=themes, reviews_path=reviews_path)

        # ── Phase 3: Report ────────────────────────────────────────────────
        if args.phase in ("report", "all"):
            from groww_pulse.phase3 import run_phase3
            md_path, txt_path = run_phase3(
                grouped_path=grouped_path,
                report_date=report_date,
            )
            logger.info(f"Pulse note: {md_path}")

        # ── Phase 4: Email ─────────────────────────────────────────────────
        if args.phase in ("email", "all"):
            from groww_pulse.phase4 import run_phase4
            eml_path = run_phase4(
                pulse_md_path=md_path,
                recipient=args.recipient,
                recipient_name=args.recipient_name,
                send=args.send,
                report_date=report_date,
            )
            action = "Sent" if args.send else "Saved (dry-run)"
            logger.info(f"{action}: {eml_path}")

        logger.info("✅ Pipeline complete!")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
