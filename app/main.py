"""Kimika FastAPI application entry point.

Start with:  uvicorn app.main:app --reload
Run pipeline once:  python -m app.pipeline --now
"""
from fastapi import FastAPI

# Load .env before anything else (python-dotenv; safe to call even if .env absent)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed yet during scaffold step

app = FastAPI(title="Kimika")


@app.get("/")
def index():
    """Placeholder root — the real page template comes in Step 8."""
    return {"status": "ok", "message": "Kimika is running. Build step 1 scaffold."}


@app.get("/health")
def health():
    return {"status": "ok"}
