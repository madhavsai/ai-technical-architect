"""AI Technical Architect — Phase 1 backend + Phase 2 agents.

Run:
    cd "AI System architect/backend"
    python -m uvicorn main:app --reload --port 8070

The frontend (public/, served separately on :8060) calls this over CORS.
"""

import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import db  # noqa: E402
import providers  # noqa: E402
from pipeline import run_pipeline  # noqa: E402

DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").strip().lower()

app = FastAPI(title="AI Technical Architect API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8060", "http://localhost:8060"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init()


STAGES = {"mvp", "growth", "large_scale"}


class BriefRequest(BaseModel):
    idea: str
    users: str = ""
    traffic: str = ""
    budget: str = ""
    availability: str = ""
    cloud: str = ""
    constraints: str = ""
    stage: str = ""  # "", "mvp", "growth", or "large_scale" - "" means let the Architect infer it
    provider: str | None = None


@app.get("/api/health")
def health():
    return {
        "default_provider": DEFAULT_PROVIDER,
        "providers": {
            "gemini": {
                "configured": providers.gemini_available(),
                "model": providers.GEMINI_MODEL,
            },
            "ollama": {
                "configured": providers.ollama_available(),
                "model": providers.OLLAMA_MODEL,
            },
        },
        "projects_generated": db.count_projects(),
    }


@app.post("/api/generate")
def generate(req: BriefRequest):
    if not req.idea.strip():
        raise HTTPException(400, "idea is required")

    provider = (req.provider or DEFAULT_PROVIDER).strip().lower()
    if provider not in ("gemini", "ollama"):
        raise HTTPException(400, f"unknown provider: {provider}")

    stage = req.stage.strip().lower()
    if stage and stage not in STAGES:
        raise HTTPException(400, f"unknown stage: {stage}")

    is_available = providers.gemini_available() if provider == "gemini" else providers.ollama_available()
    if not is_available:
        raise HTTPException(409, f"{provider} isn't configured — check /api/health")

    brief = req.model_dump(exclude={"provider"})
    brief["stage"] = stage

    try:
        result = run_pipeline(brief, provider)
    except Exception as e:
        raise HTTPException(502, str(e)) from e

    project_id = str(uuid.uuid4())
    db.save_project(project_id, provider, brief, result)

    return {"id": project_id, "provider": provider, **result}


@app.get("/api/projects")
def list_projects():
    return {"projects": db.list_projects()}


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    project = db.get_project(project_id)
    if project is None:
        raise HTTPException(404, "no project with that id")
    return project
