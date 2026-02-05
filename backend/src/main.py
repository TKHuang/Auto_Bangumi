import logging
import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from module.api import v1
from module.conf import VERSION, settings, setup_logger

setup_logger(reset=True)
logger = logging.getLogger(__name__)
uvicorn_logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": logger.handlers,
    "loggers": {
        "uvicorn": {
            "level": logger.level,
        },
        "uvicorn.access": {
            "level": "WARNING",
        },
    },
}


def create_app() -> FastAPI:
    app = FastAPI()

    # mount routers
    app.include_router(v1, prefix="/api")

    # mount /posters static directory (if exists)
    if os.path.isdir("data/posters"):
        app.mount("/posters", StaticFiles(directory="data/posters"), name="posters")

    if VERSION != "DEV_VERSION":
        # production: mount frontend dist as catchall
        if os.path.isdir("dist/assets"):
            app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")
        if os.path.isdir("dist/images"):
            app.mount("/images", StaticFiles(directory="dist/images"), name="images")
        if os.path.isdir("dist"):
            templates = Jinja2Templates(directory="dist")

            @app.get("/{path:path}")
            def html(request: Request, path: str):
                files = os.listdir("dist")
                if path in files:
                    return FileResponse(f"dist/{path}")
                else:
                    context = {"request": request}
                    return templates.TemplateResponse("index.html", context)
    else:
        # dev mode: redirect / to /docs
        @app.get("/", status_code=302, tags=["html"])
        def index():
            return RedirectResponse("/docs")

    return app


app = create_app()


if __name__ == "__main__":
    if os.getenv("IPV6"):
        host = "::"
    else:
        host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(
        app,
        host=host,
        port=settings.program.webui_port,
        log_config=uvicorn_logging_config,
    )
