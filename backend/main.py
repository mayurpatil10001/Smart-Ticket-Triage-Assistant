"""
main.py — FastAPI application entry point for Smart Ticket Triage Assistant.

Run with:
    uvicorn main:app --reload --port 8000
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure the backend directory is on the path when running directly
sys.path.insert(0, str(Path(__file__).parent))

import database
from routes.tickets import router as tickets_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated on_event — also works with TestClient)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initialising database …")
    database.init_db()
    logger.info("Database ready.")
    yield
    # shutdown: nothing to clean up for SQLite


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Smart Ticket Triage Assistant",
    description=(
        "Classifies support tickets with an LLM and generates intent-appropriate "
        "automated responses. Escalates unclassified tickets for human review."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Allow the frontend (served from any origin during dev) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(tickets_router)

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/", tags=["health"])
async def health_check():
    return {
        "status": "ok",
        "service": "Smart Ticket Triage Assistant",
        "version": "1.0.0",
    }


# ---------------------------------------------------------------------------
# Dev-mode entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

