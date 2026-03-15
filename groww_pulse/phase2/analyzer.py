"""
Phase 2: Theme Discovery (2a) and Review Classification (2b)
- 2a: Send a stratified sample to Groq → get 3-5 themes
- 2b: Classify every review into one theme (in batches of 50)
- Saves grouped_reviews-YYYY-MM-DD.json
"""

import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
SAMPLE_SIZE = 150
RETRY_SLEEP = [2, 5]


# ── 2a: Theme Discovery ────────────────────────────────────────────────────

def run_phase2a(reviews_path: Path = None) -> list:
    """
    Discover 3-5 themes from a stratified sample of reviews.

    Args:
        reviews_path: Path to Phase 1 output JSON. Uses latest if None.

    Returns:
        List of theme dicts: [{"id", "label", "description"}, ...]
    """
    from groww_pulse.config import GROQ_API_KEY, GROQ_MODEL, APP_NAME, REVIEWS_DIR

    reviews_path = reviews_path or _latest_file(REVIEWS_DIR)
    logger.info(f"Phase 2a: discovering themes from {reviews_path}")

    data = json.loads(reviews_path.read_text())
    reviews = data["reviews"]
    logger.info(f"  Loaded {len(reviews)} reviews")

    # Stratified sample: ~30 per rating level
    sample = _stratified_sample(reviews, SAMPLE_SIZE)
    sample_texts = [f"[{r['rating']}★] {r['text']}" for r in sample]

    prompt = f"""You are a product analyst at {APP_NAME}, an Indian investment app.

Given these {len(sample_texts)} user reviews, identify exactly 3 to 5 recurring themes that capture the main user pain points and praise areas.

Reviews:
{chr(10).join(f'{i+1}. {t}' for i, t in enumerate(sample_texts))}

Return ONLY a valid JSON array of theme objects (no markdown, no explanation):
[{{"id": "theme_slug", "label": "Human-Readable Label", "description": "One-line description of what this theme covers"}}]

Rules:
- Exactly 3 to 5 themes
- id must be lowercase_with_underscores
- label must be concise (2-4 words)
- description must be one sentence
- Cover distinct areas (e.g. performance, UX, features, support, security)"""

    themes = _call_groq_with_retry(prompt, GROQ_API_KEY, GROQ_MODEL, expect_json=True)

    # Validate
    if not isinstance(themes, list) or not (3 <= len(themes) <= 5):
        logger.warning(f"Unexpected theme count: {len(themes) if isinstance(themes, list) else 'not a list'}")
        themes = _fallback_themes()

    for t in themes:
        if not all(k in t for k in ("id", "label", "description")):
            logger.warning(f"Theme missing keys: {t}")
            themes = _fallback_themes()
            break

    logger.info(f"Phase 2a complete: {len(themes)} themes → {[t['label'] for t in themes]}")
    return themes


# ── 2b: Review Classification ──────────────────────────────────────────────

def run_phase2b(themes: list, reviews_path: Path = None) -> Path:
    """
    Classify every review into one of the discovered themes.

    Args:
        themes: Output of run_phase2a.
        reviews_path: Path to Phase 1 output JSON. Uses latest if None.

    Returns:
        Path to grouped_reviews-YYYY-MM-DD.json
    """
    from groww_pulse.config import GROQ_API_KEY, GROQ_MODEL, REVIEWS_DIR, REPORTS_DIR

    reviews_path = reviews_path or _latest_file(REVIEWS_DIR)
    logger.info(f"Phase 2b: classifying reviews from {reviews_path}")

    data = json.loads(reviews_path.read_text())
    reviews = data["reviews"]

    themes_json = json.dumps(themes, ensure_ascii=False)
    theme_ids = {t["id"] for t in themes}
    fallback_theme_id = themes[0]["id"]

    by_theme = {t["id"]: [] for t in themes}
    unclassified = []

    batches = [reviews[i:i + BATCH_SIZE] for i in range(0, len(reviews), BATCH_SIZE)]
    logger.info(f"  Classifying {len(reviews)} reviews in {len(batches)} batches")

    for batch_idx, batch in enumerate(batches):
        logger.info(f"  Batch {batch_idx + 1}/{len(batches)} ({len(batch)} reviews)")

        batch_payload = [{"reviewId": r["reviewId"], "text": r["text"]} for r in batch]

        prompt = f"""You are a product analyst. Classify each review into exactly one of these themes:
{themes_json}

Reviews to classify:
{json.dumps(batch_payload, ensure_ascii=False)}

Return ONLY a valid JSON array (no markdown, no explanation):
[{{"reviewId": "...", "theme_id": "..."}}]

Rules:
- Every review must appear exactly once
- theme_id must be one of: {', '.join(theme_ids)}
- Choose the most dominant theme if a review mentions multiple"""

        result = _call_groq_with_retry(prompt, GROQ_API_KEY, GROQ_MODEL, expect_json=True)

        if isinstance(result, list):
            assigned_ids = {item["reviewId"] for item in result if isinstance(item, dict)}
            for item in result:
                if not isinstance(item, dict):
                    continue
                rid = item.get("reviewId")
                tid = item.get("theme_id")
                if tid not in theme_ids:
                    tid = fallback_theme_id
                # Find original review
                original = next((r for r in batch if r["reviewId"] == rid), None)
                if original:
                    by_theme[tid].append(original)
            # Handle any reviews the LLM missed
            for r in batch:
                if r["reviewId"] not in assigned_ids:
                    unclassified.append(r)
        else:
            # Entire batch failed — assign to fallback
            for r in batch:
                unclassified.append(r)

        time.sleep(0.5)  # Rate limit buffer

    # Assign unclassified to the largest theme
    if unclassified:
        largest = max(by_theme, key=lambda k: len(by_theme[k]))
        by_theme[largest].extend(unclassified)
        logger.warning(f"  {len(unclassified)} unclassified reviews assigned to '{largest}'")

    # ── Save ───────────────────────────────────────────────────────────────
    today = datetime.now(timezone.utc).date().isoformat()
    out_path = REPORTS_DIR / f"grouped_reviews-{today}.json"

    counts = {t["id"]: len(by_theme[t["id"]]) for t in themes}
    logger.info(f"  Theme counts: {counts}")

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "themes": themes,
        "byTheme": by_theme,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    logger.info(f"Phase 2b complete → {out_path}")
    return out_path


# ── Helpers ────────────────────────────────────────────────────────────────

def _call_groq_with_retry(prompt: str, api_key: str, model: str,
                           expect_json: bool = False, retries: int = 2):
    """Call Groq API with retry and optional JSON parsing."""
    if not api_key:
        logger.warning("No GROQ_API_KEY set — returning mock response")
        if expect_json:
            return _mock_json_response(prompt)
        return ""

    try:
        from groq import Groq
    except ImportError:
        logger.error("groq package not installed")
        if expect_json:
            return _mock_json_response(prompt)
        return ""

    client = Groq(api_key=api_key)

    for attempt in range(retries + 1):
        try:
            messages = [{"role": "user", "content": prompt}]
            if attempt > 0 and expect_json:
                messages[0]["content"] += "\n\nIMPORTANT: Return ONLY valid JSON, no markdown backticks, no explanation."

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=4096,
            )
            content = response.choices[0].message.content.strip()

            if expect_json:
                # Strip markdown code fences
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                return json.loads(content)
            return content

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error (attempt {attempt + 1}): {e}")
            if attempt < retries:
                time.sleep(RETRY_SLEEP[min(attempt, len(RETRY_SLEEP) - 1)])
        except Exception as e:
            err = str(e)
            if "429" in err:
                sleep_time = RETRY_SLEEP[min(attempt, len(RETRY_SLEEP) - 1)]
                logger.warning(f"Rate limited (attempt {attempt + 1}), sleeping {sleep_time}s")
                time.sleep(sleep_time)
            else:
                logger.error(f"Groq API error: {e}")
                if attempt >= retries:
                    break

    if expect_json:
        return _mock_json_response(prompt)
    return ""


def _mock_json_response(prompt: str):
    """Return realistic mock response when no API key is available."""
    if "classify" in prompt.lower() or "reviewId" in prompt:
        # Extract review IDs from prompt and mock classify them
        import re
        ids = re.findall(r'"reviewId":\s*"([^"]+)"', prompt)
        theme_ids = ["app_performance", "ui_ux", "investment_features", "customer_support", "security_trust"]
        return [{"reviewId": rid, "theme_id": theme_ids[i % len(theme_ids)]} for i, rid in enumerate(ids)]
    else:
        return _fallback_themes()


def _fallback_themes() -> list:
    return [
        {"id": "app_performance", "label": "App Performance & Crashes", "description": "Issues with app speed, crashes, freezes, and stability."},
        {"id": "ui_ux", "label": "UI/UX & Navigation", "description": "Feedback on interface design, usability, and navigation."},
        {"id": "investment_features", "label": "Investment Features", "description": "Features related to SIPs, mutual funds, stocks, and portfolio."},
        {"id": "customer_support", "label": "Customer Support", "description": "Experiences with support quality, response time, and resolution."},
        {"id": "security_trust", "label": "Security & Trust", "description": "Concerns and praise around login security, OTP, and data safety."},
    ]


def _stratified_sample(reviews: list, n: int) -> list:
    """Sample n reviews stratified by star rating."""
    by_rating = {1: [], 2: [], 3: [], 4: [], 5: []}
    for r in reviews:
        by_rating[r["rating"]].append(r)

    per_bucket = max(1, n // 5)
    sample = []
    for rating_reviews in by_rating.values():
        sample.extend(random.sample(rating_reviews, min(per_bucket, len(rating_reviews))))

    # Top up to n
    remaining = [r for r in reviews if r not in sample]
    if len(sample) < n and remaining:
        sample.extend(random.sample(remaining, min(n - len(sample), len(remaining))))

    return sample[:n]


def _latest_file(directory: Path) -> Path:
    files = sorted(directory.glob("*.json"), reverse=True)
    if not files:
        raise FileNotFoundError(f"No JSON files found in {directory}. Run Phase 1 first.")
    return files[0]
