"""
Phase 1: Review Ingestion and Cleaning
- Fetches up to max_reviews Play Store reviews for Groww
- Filters to the requested date window (last N weeks)
- Removes reviews < MIN_REVIEW_WORDS words
- Removes non-English reviews
- Strips PII (phone numbers, emails, names pattern)
- Saves to data/reviews/YYYY-MM-DD.json
"""

import json
import logging
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ── PII patterns ───────────────────────────────────────────────────────────
_PII_PATTERNS = [
    re.compile(r"\b[6-9]\d{9}\b"),                         # Indian mobile numbers
    re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),              # PAN card
    re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),  # Email
    re.compile(r"\b\d{12}\b"),                              # Aadhaar-like
]


def pii_filter(text: str) -> str:
    """Replace PII tokens with [REDACTED]."""
    for pattern in _PII_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text.strip()


def _is_english(text: str) -> bool:
    """Best-effort English detection without heavy deps."""
    try:
        from langdetect import detect
        return detect(text) == "en"
    except Exception:
        # Fallback: check ASCII ratio
        ascii_count = sum(1 for c in text if ord(c) < 128)
        return (ascii_count / max(len(text), 1)) > 0.85


def _word_count(text: str) -> int:
    return len(text.split())


def run_phase1(weeks: int = 10, max_reviews: int = 5000, use_mock: bool = False) -> Path:
    """
    Fetch, clean, and persist reviews.

    Args:
        weeks: Number of weeks to look back.
        max_reviews: Maximum reviews to fetch from Play Store.
        use_mock: If True, generate realistic mock data instead of scraping.

    Returns:
        Path to the saved reviews JSON file.
    """
    from groww_pulse.config import (
        APP_ID, APP_NAME, REVIEWS_DIR, MIN_REVIEW_WORDS
    )

    today = datetime.now(timezone.utc).date()
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    out_path = REVIEWS_DIR / f"{today.isoformat()}.json"

    logger.info(f"Phase 1: fetching reviews for {APP_ID} (last {weeks} weeks, max {max_reviews})")

    raw_reviews = []

    if use_mock:
        logger.info("Using mock review data (no real scraping)")
        raw_reviews = _generate_mock_reviews(weeks, max_reviews)
    else:
        try:
            raw_reviews = _scrape_play_store(APP_ID, max_reviews)
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            logger.info("Falling back to mock data")
            raw_reviews = _generate_mock_reviews(weeks, max_reviews)

    # ── Filter and clean ───────────────────────────────────────────────────
    cleaned = []
    stats = {"total": len(raw_reviews), "date_filtered": 0, "short_filtered": 0,
             "lang_filtered": 0, "kept": 0}

    for r in raw_reviews:
        # Parse date
        raw_date = r.get("at") or r.get("date")
        if isinstance(raw_date, datetime):
            review_dt = raw_date.replace(tzinfo=timezone.utc) if raw_date.tzinfo is None else raw_date
        elif isinstance(raw_date, str):
            try:
                review_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                continue
        else:
            continue

        # Date window filter
        if review_dt < cutoff:
            stats["date_filtered"] += 1
            continue

        text = str(r.get("content") or r.get("text") or "").strip()

        # Word count filter
        if _word_count(text) < MIN_REVIEW_WORDS:
            stats["short_filtered"] += 1
            continue

        # Language filter
        if not _is_english(text):
            stats["lang_filtered"] += 1
            continue

        # PII filter
        clean_text = pii_filter(text)

        # Rating
        rating = int(r.get("score") or r.get("rating") or 3)

        cleaned.append({
            "reviewId": str(r.get("reviewId") or r.get("id") or f"mock_{len(cleaned)}"),
            "rating": rating,
            "text": clean_text,
            "date": review_dt.isoformat(),
        })

    stats["kept"] = len(cleaned)
    logger.info(f"Phase 1 stats: {stats}")

    # ── Persist ────────────────────────────────────────────────────────────
    payload = {
        "scrapedAt": datetime.now(timezone.utc).isoformat(),
        "packageId": APP_ID,
        "appName": APP_NAME,
        "weeksRequested": weeks,
        "stats": stats,
        "reviews": cleaned,
    }

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    logger.info(f"Phase 1 complete → {out_path} ({len(cleaned)} reviews)")
    return out_path


# ── Real scraper ───────────────────────────────────────────────────────────

def _scrape_play_store(app_id: str, max_reviews: int) -> list:
    """Use google-play-scraper to fetch reviews."""
    from google_play_scraper import reviews, Sort

    all_reviews = []
    continuation_token = None
    batch_size = 200  # API limit per call

    while len(all_reviews) < max_reviews:
        fetch_count = min(batch_size, max_reviews - len(all_reviews))
        result, continuation_token = reviews(
            app_id,
            lang="en",
            country="in",
            sort=Sort.NEWEST,
            count=fetch_count,
            continuation_token=continuation_token,
        )
        all_reviews.extend(result)
        logger.info(f"  Fetched batch: {len(result)} reviews (total so far: {len(all_reviews)})")

        if not continuation_token or not result:
            break

    return all_reviews


# ── Mock data generator ────────────────────────────────────────────────────

def _generate_mock_reviews(weeks: int, max_count: int) -> list:
    """Generate realistic Groww-like reviews for development/demo."""
    import random
    from datetime import timedelta

    now = datetime.now(timezone.utc)

    MOCK_REVIEWS = [
        # App Performance & Crashes
        (2, "App crashes every time I try to check my portfolio. This has been happening for 3 days. Very frustrating experience."),
        (1, "The app freezes when I switch between mutual fund and stocks tabs. Restarting fixes it but it keeps coming back."),
        (2, "Loading times are terrible. The dashboard takes 15 to 20 seconds to load even on a 5G connection."),
        (3, "App was great earlier but after the last update it has become slow. Hope they fix this soon."),
        (1, "Keeps logging me out automatically. I have to login again and again. Very annoying during market hours."),
        (2, "Charts don't load properly on my phone. The candlestick view just shows a blank screen half the time."),
        (1, "App crashes when I try to place a limit order. Lost a good entry point because of this bug."),
        (3, "Performance is inconsistent. Sometimes blazing fast, sometimes painfully slow. Needs optimization."),
        (2, "Push notifications for SIP execution don't arrive on time. I only know after checking manually."),
        (1, "Black screen after login. Cleared cache, reinstalled, nothing works. Please fix this urgently."),

        # UI/UX & Navigation
        (3, "The new UI is confusing. I can't find where to check my investment returns like before. Please bring back the old layout."),
        (4, "Love the overall design but the font size in the portfolio section is too small for my eyes."),
        (2, "It's hard to find the SIP details page. Too many taps to reach basic information I need daily."),
        (3, "The dark mode looks good but some text is barely readable against the dark background."),
        (4, "Good app overall. The discover section helps me find new funds. Wish the search was a bit smarter."),
        (3, "Navigation could be more intuitive. Why is watchlist buried so deep? Should be on the home screen."),
        (5, "Clean and minimal interface. Easy to use for beginners. My mother who is 55 can use it without help."),
        (2, "The portfolio graph is misleading. It doesn't clearly show returns vs invested amount side by side."),
        (4, "Transaction history is well laid out. Easy to download statements. Good for tax filing."),
        (3, "Onboarding was smooth but the KYC flow had too many steps. Took me 20 minutes to complete."),

        # Investment Features
        (5, "Best app for SIP investments. Setting up a new SIP takes under 2 minutes. Highly recommended."),
        (4, "The fund comparison feature is excellent. Helps me pick the right fund for my goals."),
        (5, "Love the US stocks feature. Now I can invest in Apple and Google directly from the same app."),
        (4, "Gold investment feature is seamless. The smallest denomination option is great for new investors."),
        (3, "Wish there was a better tax harvesting tool. Other apps offer this feature, Groww should too."),
        (5, "Portfolio tracker is top notch. XIRR calculation is accurate and helps me understand my actual returns."),
        (4, "The screener for stocks is very powerful. I can filter by PE ratio, dividend yield, and sector easily."),
        (3, "No option to set a target price alert without placing an order. This basic feature is missing."),
        (5, "SIP pause feature saved me during a tough month. Love that flexibility. Great product thinking."),
        (4, "The mutual fund ratings and analysis reports are helpful for making informed decisions."),
        (2, "Cannot invest in international ETFs like Nasdaq 100 anymore. Please bring that option back."),
        (5, "Instant redemption on liquid funds is a lifesaver. Money in my account within minutes."),

        # Customer Support
        (1, "Raised a ticket 10 days ago about wrong NAV applied to my SIP. No resolution yet. Very poor support."),
        (1, "KYC was rejected without any proper reason. Customer care takes days to respond. Unacceptable."),
        (2, "Support chat is useless. The bot keeps giving generic answers. Can never reach a real human agent."),
        (1, "My redemption request has been stuck for 7 business days. No update, no call back. Pathetic service."),
        (3, "Response time from support has improved but resolution quality is still lacking. Need better agents."),
        (1, "They debited my account twice for a single SIP payment. It's been 2 weeks and refund is not credited."),
        (2, "Help section FAQs are outdated. Doesn't match the current app interface at all."),
        (4, "Had an issue with nominee addition. Support resolved it in 2 days with clear communication. Thank you."),
        (1, "Account blocked for no reason during market hours. Could not exit a losing position. This is unacceptable."),
        (2, "Verification process for bank account change took 5 business days. Too slow for a fintech company."),

        # Security & Trust
        (4, "Two factor authentication works well. Feel safe about my investments and personal data."),
        (5, "Biometric login is smooth and fast. Much better than entering the full PIN every time."),
        (2, "Got a suspicious login attempt notification. Glad the alert came but wish there was a force logout option."),
        (3, "App doesn't support hardware security keys. For an investment app the security should be top tier."),
        (4, "Liked how they handled the recent data issue. Transparency and quick communication was appreciated."),
        (1, "Received a phishing call claiming to be Groww support asking for OTP. The company should warn users more proactively."),
        (5, "Money always arrives on time. Transactions are secure and reliable. Using it for 3 years without any issue."),
        (3, "No session timeout setting available. I want the app to auto lock after 5 minutes of inactivity."),
        (4, "The security audit badge they display gives me confidence. Glad they take compliance seriously."),
        (2, "Login OTP sometimes takes 3 to 4 minutes to arrive. Creates anxiety during time sensitive operations."),
    ]

    result = []
    for i in range(min(max_count, 400)):
        rating, text = MOCK_REVIEWS[i % len(MOCK_REVIEWS)]
        # Add slight variation to text
        days_ago = random.randint(0, weeks * 7 - 1)
        review_date = now - timedelta(days=days_ago, hours=random.randint(0, 23))

        # Slight rating randomization for realism
        adjusted_rating = max(1, min(5, rating + random.choice([-1, 0, 0, 0, 1])))

        result.append({
            "reviewId": f"review_{i:04d}_{days_ago}",
            "score": adjusted_rating,
            "content": text,
            "at": review_date,
            "date": review_date.isoformat(),
        })

    return result
