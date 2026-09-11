import time
import os
from typing import Optional, Type
from pydantic import BaseModel

import app.common.clients.variables as vr
import variables as app_vr
from app.common.clients.text_generation import TextGenerator
from app.common.exceptions import ErrorMessages, APILogicError, format_error

class MockTextGenerator(TextGenerator):
    """
    Returns static response
    """

    def __init__(self, model_name: str):
        self.model_name = model_name

    def _get_token_count(self, usage_metadata: dict, task_str: str) -> dict:
        # don't need a token count for mock implementation
        return None

    def generate_text(
        self,
        contents: str,
        system_instruction: str = None,
        response_model: Optional[Type[BaseModel]] = None,
        task_str: str = None
    ) -> dict:

        # configurable wait time
        # TODO: set this in config
        MOCK_LATENCY = float(os.getenv("MOCK_LATENCY", 1.0))
        time.sleep(MOCK_LATENCY)

        # Use the task string to find the particular task being completed and return the relevant mock response
        if task_str in vr.TASK_MAP.keys():
            mock_response = vr.TASK_MAP[task_str]
            # validate that the mock response matches the expected response schema for the task
            if response_model:
                try:
                    response_model.model_validate(mock_response)
                except Exception as e:
                    error_details = format_error(ErrorMessages.TextGeneration.MOCK_RESPONSE_VALIDATION, e)
                    raise APILogicError(error_details)
            # make sure response has the same structure as the real implementations (VertexTextGenerator)
            return {
                app_vr.generated_content_key: mock_response,
                app_vr.token_key: {"total_token_count": 0}
            }
        
        else:
            error_details = format_error(ErrorMessages.TextGeneration.NO_MOCK_RESPONSE)
            raise APILogicError(error_details)