from fastapi.responses import JSONResponse


def u_response(status_code: int, msg_en: str, msg_zh: str) -> JSONResponse:
    """
    Universal response helper for API endpoints.
    
    Args:
        status_code: HTTP status code
        msg_en: English message
        msg_zh: Chinese message
    
    Returns:
        JSONResponse with standardized format
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "msg_en": msg_en,
            "msg_zh": msg_zh,
        },
    )
