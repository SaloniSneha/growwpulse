"""
FastAPI Backend for Groww Weekly Review Pulse
Endpoints:
  GET  /health
  POST /api/run           → Trigger full pipeline
  GET  /api/pulse/latest  → Get latest pulse note
  GET  /api/status        → Pipeline run status
  GET  /api/themes/latest → Get latest themes
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("groww_pulse.api")

app = FastAPI(
    title="Groww Review Pulse API",
    description="Turns Play Store reviews into a weekly pulse note",
    version="1.0.0",
)

# ── CORS ───────────────────────────────────────────────────────────────────
cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")
cors_origins = [o.strip() for o in cors_origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory run state ────────────────────────────────────────────────────
_run_state = {
    "status": "idle",       # idle | running | done | error
    "phase": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
    "pulse_md": None,
}
_state_lock = threading.Lock()


# ── Request / Response models ──────────────────────────────────────────────

class RunRequest(BaseModel):
    weeks: int = 10
    max_reviews: int = 1000
    send_email: bool = False
    recipient: Optional[str] = None
    recipient_name: Optional[str] = None
    use_mock: bool = False


class RunResponse(BaseModel):
    message: str
    status: str


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "groww-pulse-api", "ts": datetime.now(timezone.utc).isoformat()}


@app.post("/api/run", response_model=RunResponse)
def run_pipeline(req: RunRequest, background_tasks: BackgroundTasks):
    with _state_lock:
        if _run_state["status"] == "running":
            raise HTTPException(status_code=409, detail="A pipeline run is already in progress.")
        _run_state.update({
            "status": "running",
            "phase": "starting",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "error": None,
            "pulse_md": None,
        })

    background_tasks.add_task(_run_pipeline_bg, req)
    return RunResponse(message="Pipeline started", status="running")


@app.get("/api/status")
def get_status():
    with _state_lock:
        return dict(_run_state)


@app.get("/api/pulse/latest")
def get_latest_pulse():
    """Return the latest pulse note as markdown text."""
    from groww_pulse.config import REPORTS_DIR
    files = sorted(REPORTS_DIR.glob("pulse-*.md"), reverse=True)
    if not files:
        raise HTTPException(status_code=404, detail="No pulse note found. Run the pipeline first.")

    latest = files[0]
    content = latest.read_text(encoding="utf-8")
    date_str = latest.stem.replace("pulse-", "")

    return {
        "date": date_str,
        "filename": latest.name,
        "content": content,
    }


@app.get("/api/themes/latest")
def get_latest_themes():
    """Return the latest themes and review counts."""
    from groww_pulse.config import REPORTS_DIR
    files = sorted(REPORTS_DIR.glob("grouped_reviews-*.json"), reverse=True)
    if not files:
        raise HTTPException(status_code=404, detail="No grouped reviews found. Run the pipeline first.")

    data = json.loads(files[0].read_text())
    themes = data.get("themes", [])
    by_theme = data.get("byTheme", {})

    result = []
    for t in themes:
        result.append({
            "id": t["id"],
            "label": t["label"],
            "description": t["description"],
            "count": len(by_theme.get(t["id"], [])),
        })

    return {
        "date": files[0].stem.replace("grouped_reviews-", ""),
        "themes": sorted(result, key=lambda x: x["count"], reverse=True),
    }


@app.get("/api/reviews/stats")
def get_review_stats():
    """Return stats from the latest review file."""
    from groww_pulse.config import REVIEWS_DIR
    files = sorted(REVIEWS_DIR.glob("*.json"), reverse=True)
    if not files:
        raise HTTPException(status_code=404, detail="No reviews found. Run Phase 1 first.")

    data = json.loads(files[0].read_text())
    reviews = data.get("reviews", [])

    rating_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in reviews:
        rating_dist[r["rating"]] = rating_dist.get(r["rating"], 0) + 1

    return {
        "total": len(reviews),
        "scrapedAt": data.get("scrapedAt"),
        "weeksRequested": data.get("weeksRequested"),
        "ratingDistribution": rating_dist,
        "avgRating": round(sum(r["rating"] * c for r, c in zip(range(1, 6), rating_dist.values())) / max(len(reviews), 1), 2),
    }


@app.get("/api/eml/latest")
def get_latest_eml():
    """Return the latest email draft as text."""
    from groww_pulse.config import REPORTS_DIR
    files = sorted(REPORTS_DIR.glob("pulse-*.eml"), reverse=True)
    if not files:
        raise HTTPException(status_code=404, detail="No email draft found. Run Phase 4 first.")
    return {"filename": files[0].name, "content": files[0].read_text(errors="replace")}


# ── Background pipeline runner ─────────────────────────────────────────────

def _run_pipeline_bg(req: RunRequest):
    """Run all 4 phases in a background thread."""
    try:
        def update(phase):
            with _state_lock:
                _run_state["phase"] = phase
            logger.info(f"Pipeline phase: {phase}")

        update("phase1_scrape")
        from groww_pulse.phase1 import run_phase1
        reviews_path = run_phase1(weeks=req.weeks, max_reviews=req.max_reviews, use_mock=req.use_mock)

        update("phase2a_themes")
        from groww_pulse.phase2 import run_phase2a
        themes = run_phase2a(reviews_path=reviews_path)

        update("phase2b_classify")
        from groww_pulse.phase2 import run_phase2b
        grouped_path = run_phase2b(themes=themes, reviews_path=reviews_path)

        update("phase3_report")
        from groww_pulse.phase3 import run_phase3
        md_path, txt_path = run_phase3(grouped_path=grouped_path)

        update("phase4_email")
        from groww_pulse.phase4 import run_phase4
        run_phase4(
            pulse_md_path=md_path,
            recipient=req.recipient,
            recipient_name=req.recipient_name,
            send=req.send_email,
        )

        with _state_lock:
            _run_state.update({
                "status": "done",
                "phase": "complete",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "pulse_md": md_path.read_text(encoding="utf-8"),
            })
        logger.info("✅ Background pipeline complete")

    except Exception as e:
        logger.error(f"Background pipeline failed: {e}", exc_info=True)
        with _state_lock:
            _run_state.update({
                "status": "error",
                "phase": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            })


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
