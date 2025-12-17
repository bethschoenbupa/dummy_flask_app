from pydantic import BaseModel, Field, ConfigDict

class ErrorData(BaseModel):
    code: int
    http_code: int = Field(
        alias="httpCode"
    )
    error_title: str = Field(
        alias="errorTitle"
    )
    detail: str

    model_config = ConfigDict(
        populate_by_name=True,
    )