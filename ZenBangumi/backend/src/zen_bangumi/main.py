"""ZenBangumi FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from zen_bangumi.api.auth import router as auth_router
from zen_bangumi.api.bangumi import router as bangumi_router
from zen_bangumi.config.loader import ConfigLoader
from zen_bangumi.database.engine import create_all_tables, engine
from zen_bangumi.domain.models.user import User
from zen_bangumi.services.user import create_user

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ZenBangumi application...")
    
    await create_all_tables()
    logger.info("Database tables created/verified")
    
    config = ConfigLoader.load()
    logger.info(f"Configuration loaded: webui_port={config.program.webui_port}")
    
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_factory() as session:
        stmt = select(User)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        if not users:
            logger.info("No users found, creating default admin user")
            await create_user("admin", "admin", session)
            await session.commit()
            logger.warning("Default admin user created: username=admin, password=admin")
            logger.warning("IMPORTANT: Please change the default password immediately!")
    
    logger.info("ZenBangumi startup complete")
    
    yield
    
    logger.info("Shutting down ZenBangumi...")
    await engine.dispose()


app = FastAPI(
    title="ZenBangumi",
    description="Modern anime auto-download and management system",
    version="0.1.0",
    lifespan=lifespan,
)


class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        async with async_session_factory() as session:
            request.state.db = session
            response = await call_next(request)
        
        return response


app.add_middleware(DBSessionMiddleware)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    return JSONResponse(
        status_code=401,
        content={"detail": "Unauthorized"},
    )


app.include_router(auth_router)
app.include_router(bangumi_router)
