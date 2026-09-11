from pydantic import BaseModel, Field, ConfigDict
from typing import Generic, TypeVar, Dict
from enum import Enum

class Status(str, Enum):
    Success = "SUCCESS"
    Failed = "FAILED"

DataType = TypeVar('DataType')

class RouteData(BaseModel, Generic[DataType]):
    createdAt: str
    timezone: str
    generatedContent: DataType

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

class Metadata(BaseModel):
    model: str #Dict[str, str]
    prompts: Dict[str, float]
    tokens: Dict[str, float]

class LLMProvider(str, Enum):
  vertex = "vertex"
  azure = "azure"

class AIRequestContext(BaseModel):
  provider: LLMProvider = LLMProvider.vertex.value
  shadow_mode: bool = False