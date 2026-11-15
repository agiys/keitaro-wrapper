from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.errors import register_error_handlers
from app.routers import campaigns, catalog

app = FastAPI(title="Keitaro wrapper")
register_error_handlers(app)
app.include_router(catalog.router)
app.include_router(campaigns.router)
app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "static", html=True), name="static")
