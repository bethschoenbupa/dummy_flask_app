#### PYDANTIC SCHEMAS ####
# Author: Bethany Schoen
# Date: 17th December 2025
###########################
# Request input validation
###########################

from pydantic import (    
    BaseModel,
    field_validator,
    field_serializer,
    Field,
    ConfigDict,
    ValidationError
)
from typing import Optional, TypeVar, Generic, Dict
from datetime import datetime 
from enum import Enum
from app.common.exceptions import ErrorMessages, format_error, APILogicError
from app.common.schemas import ErrorData, Metadata

# =========================== #
# --- API Response models --- #
# =========================== #

class Status(str, Enum):
    Success = "SUCCESS"
    Failed = "FAILED"

class InferenceMetadata(BaseModel):
    """
    Pydantic model for InferenceMetadata, based on the Avro schema and
    extended with creation timestamp information.
    """
    
    # --- Fields from Avro Schema ---
    request_id: str = Field(
        alias="requestId",
        description="Request ID, typically the traceId from the request."
    )
    
    api_version: str = Field(
        alias="apiVersion",
        description="AI inference API version."
    )
    
    status: Status = Field(
        description="The status of the API response (e.g., 'success')."
    )
    
    model: Optional[str] = Field(
        description="Identifier for the inference model that was used.",
        default=None
    )
    
    prompts: Optional[Dict[str, int]] = Field(
        description="A map of prompt names to their versions.",
        default=None
    )
    
    tokens: Optional[int] = Field(
        description="Total token count used for the inference.",
        default=None
    )
    
    @field_serializer("status")
    def serialize_status(self, status: Status, _info):
        return status.value

    model_config = ConfigDict(
        populate_by_name=True,
    )

APIDataType = TypeVar('DataType')

class ApiResponse(BaseModel, Generic[APIDataType]):
    """
    The final, generic, reusable API response envelope.
    Either 'result' or 'failures' must be populated (not both None).
    Both can be populated at the same time.
    """
    result: Optional[APIDataType] = None
    failures: Optional[ErrorData] = None
    inference_metadata: InferenceMetadata = Field(
        alias="inferenceMetadata",
        description="Metadata about the inference operation."
    )
    
    model_config = ConfigDict(populate_by_name=True)

    @field_validator('failures', mode='after')
    def validate_result_or_failures(cls, v, values):
        result = values.data.get('result')
        if result is None and v is None:
            raise ValueError("Either 'result' or 'failures' must be populated (not both None).")
        return v

# ============================= #
# --- Reusable input models --- #
# ============================= #

class NameRequestModel(BaseModel):
    name: str

class DateRequestModel(BaseModel):
    date: datetime
        
    @field_validator("date", mode="before")
    @classmethod
    def ensure_date_structure(cls, date):
        if isinstance(date, str):
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                return date_obj
            except Exception as e:
                error_details = format_error(ErrorMessages.App.DATE_CONVERSION, exception=e)
                raise APILogicError(error_details)
        elif isinstance(date, datetime):
            return date
        else:
            raise ValidationError("Datetime not recognised")

# ========================================= #
# --- Reusable service response models ---  #
# ========================================= #

DataType = TypeVar('DataType')

class ServiceResult(BaseModel, Generic[DataType]):
    data: DataType
    metadata: Metadata
    partial_result: Optional[bool] = Field(
        default=False,
        alias="partialResult",
        description="Indicates if the result is partial due to an error or timeout."
    )
    
    model_config = ConfigDict(
        populate_by_name=True,
    )
    
# ============================= #
# --- Haiku endpoint models --- #
# ============================= #

class UserInfoModel(NameRequestModel, DateRequestModel):
    pass

class HaikuRequestModel(BaseModel):
    user_info: UserInfoModel = Field(
        ...,
        alias="userInfo",
        description="Information about the user making the request."
    )

class HaikuResponseModel(BaseModel):
    is_birthday: bool = Field(
        ...,
        alias="isBirthday",
        description="Indicates if today is the user's birthday"
    )
    haiku: str

    model_config = ConfigDict(
        populate_by_name=True,
    )

HaikuServiceResult = ServiceResult[HaikuResponseModel]  

# ================================= #
# --- Next Year endpoint models --- #
# ================================= #

# Paste notebook code here