"""Log API endpoints."""
import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import Response, JSONResponse

from module.api.middleware.auth import get_current_user
from module.conf import LOG_PATH

router = APIRouter(prefix="/log", tags=["log"])


def _read_last_100_lines() -> str:
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
        return "".join(lines[-100:])


@router.get("", response_class=Response, dependencies=[Depends(get_current_user)])
async def get_log():
    if LOG_PATH.exists():
        content = await asyncio.to_thread(_read_last_100_lines)
        return Response(content, media_type="text/plain")
    else:
        return Response("Log file not found", status_code=404)


@router.delete("/clear", dependencies=[Depends(get_current_user)])
async def clear_log():
    if LOG_PATH.exists():
        await asyncio.to_thread(LOG_PATH.write_text, "")
        return JSONResponse(
            status_code=200,
            content={"msg_en": "Log cleared successfully.", "msg_zh": "日志清除成功。"},
        )
    else:
        return JSONResponse(
            status_code=404,
            content={"msg_en": "Log file not found.", "msg_zh": "日志文件未找到。"},
        )
