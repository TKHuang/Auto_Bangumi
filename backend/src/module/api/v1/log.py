"""Log API endpoints."""
from fastapi import APIRouter, Depends
from fastapi.responses import Response, JSONResponse

from module.api.middleware.auth import get_current_user
from module.conf import LOG_PATH

router = APIRouter(prefix="/log", tags=["log"])


@router.get("", response_class=Response, dependencies=[Depends(get_current_user)])
async def get_log():
    """Get last 100 lines of log file as plain text."""
    if LOG_PATH.exists():
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            last_100_lines = "".join(lines[-100:])
            return Response(last_100_lines, media_type="text/plain")
    else:
        return Response("Log file not found", status_code=404)


@router.get("/clear", dependencies=[Depends(get_current_user)])
async def clear_log():
    """Clear log file and return success/error message."""
    if LOG_PATH.exists():
        LOG_PATH.write_text("")
        return JSONResponse(
            status_code=200,
            content={"msg_en": "Log cleared successfully.", "msg_zh": "日志清除成功。"},
        )
    else:
        return JSONResponse(
            status_code=406,
            content={"msg_en": "Log file not found.", "msg_zh": "日志文件未找到。"},
        )
