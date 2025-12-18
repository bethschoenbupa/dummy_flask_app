#### PYDANTIC SCHEMAS ####
# Author: Bethany Schoen
# Date: 17th December 2025
###########################
# Request input validation
###########################

from pydantic import (    
    BaseModel,
    field_validator,
    Field,
    ConfigDict,
    ValidationError
)
from typing import Optional, TypeVar, Generic
from datetime import datetime 
import uuid

from app.common.exceptions import ErrorMessages, format_error, APILogicError
from app.common.schemas import ErrorData

# ====================== #
# --- Generic models --- #
# ====================== #

DataType = TypeVar('DataType')

# allows all services to return a consistent structure
class ServiceResult(BaseModel, Generic[DataType]):
    data: DataType

class InferenceMetadata(BaseModel):
    """
    Information about the request that was completed
    """
    
    request_id: str = Field(
        alias="requestId",
        description="Request ID, typically the traceId from the request."
    )
    
    route: str = Field(
        description="The endpoint that has been called"
    )

    api_version: str = Field(
        alias="apiVersion",
        description="The api version"
    )
    
    status: str = Field(
        description="The status of the API response (e.g., 'success')."
    )

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
            
        
    
# ============================= #
# --- Haiku endpoint models --- #
# ============================= #

class HaikuRequestModel(NameRequestModel, DateRequestModel):
    pass

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

# class NextYearRequestModel(DateRequestModel):
#     pass

# class NextYearResponseModel(BaseModel):
#     next_year_date: str = Field(
#         ...,
#         alias="nextYearDate",
#         description="The requesters birthday next year"
#     )

#     @field_serializer("next_year_date", mode="wrap")
#     @classmethod
#     def format_next_year_date(cls, date):
#         date_obj = datetime.strptime(date, "%Y-%m-%d")
#         return date_obj.strftime("%Y-%m-%d")
    
#     model_config = ConfigDict(
#         populate_by_name=True,
#     )

