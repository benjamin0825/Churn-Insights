"""FastAPI application: JSON API under /api, the built React app everywhere else.

    uvicorn app.main:app --reload            # from backend/
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import get_settings
from .db import init_engine
from .routers import about, admin, auth, campaigns, careers, customers, dashboard, data, jobs, models, monitoring, overview


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    init_engine()

    app = FastAPI(title="Churn Service", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])
    for router in (auth.router, data.router, jobs.router, overview.router, customers.router, dashboard.router,
                   campaigns.router, models.router, monitoring.router, admin.router, admin.public, careers.public,
                   careers.admin, about.public, about.admin):
        app.include_router(router)

    @app.get("/api/health")
    def health() -> dict:
        from churn_ml import kernels

        return {"status": "ok", "version": __version__, "kernel_backend": kernels.BACKEND}

    dist = settings.frontend_dist
    if (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404, "Not found")
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and dist.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")  # client-side routing

    return app


app = create_app()
