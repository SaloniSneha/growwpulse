from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import subprocess
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("groww_pulse.server")

app = FastAPI(title="Groww Pulse API")

class PipelineRequest(BaseModel):
    phase: str = "all"
    weeks: int = 10
    max_reviews: int = 5000
    send: bool = False
    recipient: str | None = None
    recipient_name: str | None = None
    date: str | None = None
    mock: bool = False

pipeline_status = {"running": False, "last_result": None}

def run_pipeline(req: PipelineRequest):
    pipeline_status["running"] = True
    try:
        cmd = [
            "python", "-m", "groww_pulse.main",
            "--phase", req.phase,
            "--weeks", str(req.weeks),
            "--max-reviews", str(req.max_reviews),
        ]
        if req.send:
            cmd.append("--send")
        if req.recipient:
            cmd += ["--recipient", req.recipient]
        if req.recipient_name:
            cmd += ["--recipient-name", req.recipient_name]
        if req.date:
            cmd += ["--date", req.date]
        if req.mock:
            cmd.append("--mock")

        result = subprocess.run(cmd, capture_output=True, text=True)
        pipeline_status["last_result"] = {
            "returncode": result.returncode,
            "stdout": result.stdout[-3000:], # last 3000 chars
            "stderr": result.stderr[-3000:],
        }
        logger.info(f"Pipeline finished with code {result.returncode}")
    except Exception as e:
        pipeline_status["last_result"] = {"error": str(e)}
        logger.error(f"Pipeline error: {e}")
    finally:
        pipeline_status["running"] = False


@app.get("/")
def health():
    return {"status": "ok", "service": "Groww Pulse API"}

@app.get("/status")
def status():
    return pipeline_status

@app.post("/run")
def trigger_pipeline(req: PipelineRequest, background_tasks: BackgroundTasks):
    if pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    background_tasks.add_task(run_pipeline, req)
    return {"status": "started", "config": req.model_dump()}
