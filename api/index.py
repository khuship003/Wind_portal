"""Vercel serverless entrypoint: exposes the Flask app (all routes start with /api)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.main import create_app  # noqa: E402

app = create_app()
