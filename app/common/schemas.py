from pydantic import BaseModel, Field, ConfigDict
from typing import Generic, TypeVar, Dict
from enum import Enum
from typing import Optional

class CacheOutcome(str, Enum):
    HIT = "hit"
    MISS = "miss"
    BYPASS = "bypass" # cache not used, regardless of circumstances (e.g., shadow mode, non-target provider, config disabled, etc.)

class CacheMetadata(BaseModel):
    outcome: CacheOutcome = CacheOutcome.BYPASS
    original_request_id: Optional[str] = None
    cache_key: Optional[str] = None
    phase: Optional[str] = None
    bypass_reason: Optional[str] = None
    wait_ms: Optional[float] = None

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
    cache_metadata: Optional[CacheMetadata] = None

class LLMProvider(str, Enum):
  vertex = "vertex"
  azure = "azure"

class AIRequestContext(BaseModel):
  provider: LLMProvider = LLMProvider.vertex.value
  shadow_mode: bool = False
