from pydantic import BaseModel, Field


class ResponseModel(BaseModel):
    status: bool = Field(..., example=True)
    status_code: int = Field(..., example=200)
    msg_en: str
    msg_zh: str
    error_type: str | None = Field(default=None, description="Error type identifier")
    existing_bangumi: dict | None = Field(
        default=None, description="Existing bangumi data for duplicate errors"
    )


class APIResponse(BaseModel):
    status: bool = Field(..., example=True)
    msg_en: str = Field(..., example="Success")
    msg_zh: str = Field(..., example="成功")