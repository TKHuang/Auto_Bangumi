import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.v1 import auth, bangumi, check, config, log, program, rss, search
from module.conf import VERSION, settings, setup_logger
from module.database.engine import AsyncSessionLocal, engine
from module.domain.models.base import Base
from module.domain.models.user import User
from module.repositories.user import UserRepository
from module.scheduler.engine import AsyncScheduler
from module.scheduler.jobs.rename import rename_job
from module.scheduler.jobs.rss_refresh import rss_refresh_job
from module.security.password import hash_password

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

scheduler: AsyncScheduler | None = None


def _run_migrations(connection):
    from sqlalchemy import text

    cursor = connection.execute(text("PRAGMA table_info(rssitem)"))
    rss_columns = [row[1] for row in cursor.fetchall()]
    if "last_update" not in rss_columns:
        connection.execute(text("ALTER TABLE rssitem ADD COLUMN last_update TEXT"))
        connection.execute(text("ALTER TABLE rssitem ADD COLUMN last_status TEXT"))
        connection.execute(text("ALTER TABLE rssitem ADD COLUMN last_error TEXT"))

    cursor = connection.execute(text("PRAGMA table_info(bangumi)"))
    bangumi_columns = [row[1] for row in cursor.fetchall()]

    if "rss_id" not in bangumi_columns:
        logger.info("[Migration] Adding rss_id column to bangumi table")
        connection.execute(text("ALTER TABLE bangumi ADD COLUMN rss_id INTEGER REFERENCES rssitem(id)"))

    if "pending_review" not in bangumi_columns:
        logger.info("[Migration] Adding pending_review column to bangumi table")
        connection.execute(text("ALTER TABLE bangumi ADD COLUMN pending_review INTEGER DEFAULT 0"))

    if "global_filter_matches" not in bangumi_columns:
        logger.info("[Migration] Adding global_filter_matches column to bangumi table")
        connection.execute(text("ALTER TABLE bangumi ADD COLUMN global_filter_matches TEXT"))

    cursor = connection.execute(text("PRAGMA table_info(torrent)"))
    torrent_columns = [row[1] for row in cursor.fetchall()]
    if "hash" not in torrent_columns:
        connection.execute(text("ALTER TABLE torrent ADD COLUMN hash TEXT"))

    if "renamed_at" not in torrent_columns:
        logger.info("[Migration] Adding renamed_at column to torrent table")
        connection.execute(text("ALTER TABLE torrent ADD COLUMN renamed_at TEXT"))
    if "renamed_file_count" not in torrent_columns:
        logger.info("[Migration] Adding renamed_file_count column to torrent table")
        connection.execute(text("ALTER TABLE torrent ADD COLUMN renamed_file_count INTEGER"))

    connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_torrent_hash_bangumi "
        "ON torrent (hash, bangumi_id) WHERE hash IS NOT NULL"
    ))

    result = connection.execute(
        text("UPDATE bangumi SET group_name = 'Unknown' WHERE group_name IS NULL OR group_name = ''")
    )
    if result.rowcount > 0:
        logger.info(f"[Migration] Updated {result.rowcount} bangumi records with NULL/empty group_name to 'Unknown'")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    logger.info("Starting application...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository(session)
        existing_users = await user_repo.get_all()
        if not existing_users:
            await user_repo.create(
                {
                    "username": "admin",
                    "password": hash_password("adminadmin"),
                }
            )
            await session.commit()
            logger.info("Default user created (admin/adminadmin)")
        else:
            logger.info("Users exist, skipping default user creation")

    async with engine.begin() as conn:
        await conn.run_sync(_run_migrations)
    logger.info("Database migrations applied")

    scheduler = AsyncScheduler()
    await scheduler.start()
    logger.info("Scheduler started")

    await scheduler.add_schedule(
        rename_job,
        trigger="interval",
        id="rename",
        seconds=settings.program.rename_time,
    )
    await scheduler.add_schedule(
        rss_refresh_job,
        trigger="interval",
        id="rss_refresh",
        seconds=settings.program.rss_time,
    )
    logger.info(
        f"Scheduled jobs: rename ({settings.program.rename_time}s), "
        f"rss_refresh ({settings.program.rss_time}s)"
    )

    from module.api.v1.program import set_scheduler

    set_scheduler(scheduler)

    yield

    if scheduler:
        await scheduler.stop()
        logger.info("Scheduler stopped")
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="Auto Bangumi", version=VERSION)

    cors_origins_env = os.getenv("CORS_ORIGINS", "")
    cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()] if cors_origins_env else []
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "PUT"],
            allow_headers=["Content-Type"],
        )

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(bangumi.router, prefix="/api/v1")
    app.include_router(check.router, prefix="/api/v1")
    app.include_router(config.router, prefix="/api/v1")
    app.include_router(log.router, prefix="/api/v1")
    app.include_router(program.router, prefix="/api/v1")
    app.include_router(rss.router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")

    os.makedirs("data/posters", exist_ok=True)
    app.mount("/posters", StaticFiles(directory="data/posters"), name="posters")

    if VERSION != "DEV_VERSION":
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
