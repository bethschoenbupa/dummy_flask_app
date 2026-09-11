from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from typing import List, Literal, Annotated
from enum import Enum

# --- BIRTHDAY HAIKU ---

HAIKU_KEY = "haiku"

class HaikuResponse(BaseModel):
    """
    A simple model to hold a generated haiku string.
    """
    
    haiku: str = Field(
        alias=HAIKU_KEY,
        description="The generated haiku"
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )