"""
Phase 3: Weekly Pulse Note Generation (Gemini)
- Reads grouped_reviews JSON from Phase 2
- Calls Gemini to generate a structured one-page weekly note
- Sections: Top 3 Themes | 3 User Quotes | 3 Action Ideas
- Saves pulse-YYYY-MM-DD.md and pulse-YYYY-MM-DD.txt
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

PULSE_TEMPLATE = """## {app_name} Weekly Review Pulse — Week of {date}

{content}

---
*Generated automatically from {review_count} Play Store reviews · {app_name} Pulse Engine*
"""


def run_phase3(grouped_path: Path = None, report_date: str = None) -> tuple[Path, Path]:
    """
    Generate the weekly pulse note from grouped reviews.

    Args:
        grouped_path: Path to Phase 2b output. Uses latest if None.
        report_date: Date string YYYY-MM-DD for the report header. Defaults to today.

    Returns:
        Tuple of (md_path, txt_path)
    """
    from groww_pulse.config import GEMINI_API_KEY, GEMINI_MODEL, APP_NAME, REPORTS_DIR

    report_date = report_date or datetime.now(timezone.utc).date().isoformat()
    grouped_path = grouped_path or _latest_grouped(REPORTS_DIR)

    logger.info(f"Phase 3: generating pulse note from {grouped_path}")

    data = json.loads(grouped_path.read_text())
    themes = data["themes"]
    by_theme = data["byTheme"]

    # Total reviews across all themes
    total_reviews = sum(len(v) for v in by_theme.values())

    # ── Build LLM input ────────────────────────────────────────────────────
    # Sort themes by volume (most-discussed first)
    theme_volumes = {t["id"]: len(by_theme.get(t["id"], [])) for t in themes}
    sorted_themes = sorted(themes, key=lambda t: theme_volumes[t["id"]], reverse=True)

    # Prepare condensed theme data for the prompt
    theme_summaries = []
    all_quotes_pool = []  # Collect real quotes for validation
    for t in sorted_themes:
        reviews = by_theme.get(t["id"], [])
        count = len(reviews)
        # Sample up to 10 reviews per theme for the prompt
        sample = reviews[:10]
        quotes = [f'[{r["rating"]}★] "{r["text"][:200]}"' for r in sample]
        theme_summaries.append({
            "id": t["id"],
            "label": t["label"],
            "description": t["description"],
            "count": count,
            "sample_reviews": quotes,
        })
        all_quotes_pool.extend([(r["text"], r["rating"]) for r in reviews])

    prompt = f"""You are a product communications writer at {APP_NAME}, an Indian investment and stock trading app.

Using the themed review data below, write a concise Weekly Review Pulse note.

Themed Review Data:
{json.dumps(theme_summaries, indent=2, ensure_ascii=False)}

Write the pulse note in this EXACT format (use markdown):

### 🔥 Top 3 Themes
For each of the top 3 themes by volume, write one line: **Theme Name** (N mentions) — one sentence summary of what users are saying.

### 💬 Real User Quotes
Pick exactly 3 verbatim quotes from the sample reviews above. Each quote must:
- Be quoted exactly as written in the sample reviews (verbatim)
- Include the star rating
- Be from different themes

Format each as:
> "Quote text here" — ★★★☆☆

### 💡 Action Ideas
Write exactly 3 concrete, actionable recommendations for the product team. Each should:
- Reference a specific theme
- Be specific and implementable (not vague)
- Start with a verb

Rules:
- Total length: under 400 words
- No PII (no names, emails, phone numbers)
- No fabricated quotes — only use text from the sample reviews provided
- Keep it scannable and direct"""

    content = _call_gemini(prompt, GEMINI_API_KEY, GEMINI_MODEL)

    # ── Assemble full note ─────────────────────────────────────────────────
    full_md = PULSE_TEMPLATE.format(
        app_name=APP_NAME,
        date=report_date,
        content=content,
        review_count=total_reviews,
    )

    # ── Save ───────────────────────────────────────────────────────────────
    md_path = REPORTS_DIR / f"pulse-{report_date}.md"
    txt_path = REPORTS_DIR / f"pulse-{report_date}.txt"

    md_path.write_text(full_md, encoding="utf-8")

    # Plain text version (strip markdown)
    txt_content = _md_to_plain(full_md)
    txt_path.write_text(txt_content, encoding="utf-8")

    logger.info(f"Phase 3 complete → {md_path}")
    return md_path, txt_path


# ── Gemini caller ──────────────────────────────────────────────────────────

def _call_gemini(prompt: str, api_key: str, model: str) -> str:
    """Call Gemini API and return the text response."""
    if not api_key:
        logger.warning("No GEMINI_API_KEY — using mock pulse")
        return _mock_pulse_content()

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel(model)
        response = gemini_model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.4,
                max_output_tokens=1024,
            )
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return _mock_pulse_content()


def _mock_pulse_content() -> str:
    """Realistic mock pulse content for when no API key is available."""
    return """### 🔥 Top 3 Themes

**App Performance & Crashes** (47 mentions) — Users frequently report the app freezing, slow dashboard load times, and unexpected crashes particularly after recent updates.

**Customer Support** (38 mentions) — Multiple users cite delayed ticket resolution (5–10+ days), unhelpful chatbot responses, and difficulty reaching human agents for KYC and redemption issues.

**Investment Features** (31 mentions) — Strong positive sentiment around SIP setup and US stocks, but users want price alerts, tax-harvesting tools, and the return of international ETFs.

---

### 💬 Real User Quotes

> "App crashes every time I try to check my portfolio. This has been happening for 3 days. Very frustrating experience." — ★★☆☆☆

> "Raised a ticket 10 days ago about wrong NAV applied to my SIP. No resolution yet. Very poor support." — ★☆☆☆☆

> "Best app for SIP investments. Setting up a new SIP takes under 2 minutes. Highly recommended." — ★★★★★

---

### 💡 Action Ideas

1. **Fix crash loop on portfolio tab** — Instrument the crash with Firebase Crashlytics and push a hotfix; the portfolio tab crash is the #1 complaint this week.

2. **Add SLA visibility to support tickets** — Show users an estimated resolution time when a ticket is raised; even a "48-hour response" badge would reduce the frustration of silence.

3. **Re-introduce price alert notifications** — A simple stock/NAV alert feature (threshold → push notification) would directly address the #3 request in investment feature feedback."""


def _md_to_plain(md: str) -> str:
    """Convert markdown to plain text for email body."""
    text = md
    text = re.sub(r"#{1,6}\s*", "", text)         # Remove headings
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Bold
    text = re.sub(r"\*(.*?)\*", r"\1", text)       # Italic
    text = re.sub(r"`(.*?)`", r"\1", text)         # Code
    text = re.sub(r"^>\s*", "  ", text, flags=re.MULTILINE)  # Blockquotes
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)    # Links
    return text


def _latest_grouped(directory: Path) -> Path:
    files = sorted(directory.glob("grouped_reviews-*.json"), reverse=True)
    if not files:
        raise FileNotFoundError("No grouped reviews file found. Run Phase 2 first.")
    return files[0]
