import logging
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.config import AppSettings
from backend.router import health_router, research_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logging.getLogger("mult_agents").setLevel(logging.INFO)
logging.getLogger("backend").setLevel(logging.INFO)


def create_app() -> FastAPI:
    settings = AppSettings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(research_router)
    @app.get("/api/local-status")
    def local_status():
        from dotenv import dotenv_values
        root = Path(__file__).resolve().parents[1]
        values = {**dotenv_values(root / ".env"), **os.environ}
        def configured(name):
            value = str(values.get(name) or "").strip()
            return bool(value) and not value.lower().startswith(("your", "change_me", "replace"))
        def reachable(host, port):
            try:
                with socket.create_connection((host, port), timeout=0.5):
                    return True
            except (OSError, ValueError, TypeError):
                return False
        try:
            postgres = urlparse(str(values.get("POSTGRES_DSN") or ""))
            postgres_reachable = reachable(postgres.hostname or "127.0.0.1", postgres.port or 5432)
        except ValueError:
            postgres_reachable = False
        return {"dashscope_configured": configured("DASHSCOPE_API_KEY"),
                "bocha_configured": configured("BOCHA_API_KEY"),
                "postgres_reachable": postgres_reachable,
                "milvus_reachable": reachable(values.get("MILVUS_HOST") or "127.0.0.1", values.get("MILVUS_PORT") or 19530)}
    frontend = Path(__file__).resolve().parents[1] / "front" / "agent_front" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()


if __name__ == "__main__":
    runtime_settings = AppSettings()
    uvicorn.run(
        "app_main:app",
        host=runtime_settings.host,
        port=runtime_settings.port,
        reload=runtime_settings.app_env == "development",
    )
