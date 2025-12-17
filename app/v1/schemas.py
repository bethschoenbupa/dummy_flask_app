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
    ConfigDict
)
from datetime import datetime 
from app.common.exceptions import ErrorMessages

# --- Reusable input models --- #

class NameRequestModel(BaseModel):
    name: str

class DateRequestModel(BaseModel):
    date: str
        
    @field_validator("date", mode="before")
    @classmethod
    def ensure_date_structure(cls, date):
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        except Exception as e:
            raise ValueError(ErrorMessages.App.DATE_CONVERSION.error)
            
        return date
    
# --- Haiku endpoint models --- #

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

# --- Next Year endpoint models --- #

class NextYearRequestModel(DateRequestModel):
    pass

class NextYearResponseModel(BaseModel):
    next_year_date: str = Field(
        ...,
        alias="nextYearDate",
        description="The requesters birthday next year"
    )

    @field_serializer("next_year_date", mode="before")
    @classmethod
    def format_next_year_date(cls, date):
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        return date_obj.strftime("%Y-%m-%d")
    
    model_config = ConfigDict(
        populate_by_name=True,
    )