import os
import json
from dotenv import load_dotenv
#from openai import AzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, RetryCallState
from typing import Optional, Type
from pydantic import BaseModel

from app.common.clients.text_generation import TextGenerator
import app.common.clients.variables as vr
from app.common.exceptions import ErrorMessages, APILogicError, format_error
import variables as app_vr
from log import logger

load_dotenv()

def log_retry(retry_state: RetryCallState):
    """Logs a retry attempt."""
    logger.warning(
        f"Retrying {retry_state.fn.__name__} due to {retry_state.outcome.exception()}. "
        f"Attempt {retry_state.attempt_number} will wait {retry_state.next_action.sleep} seconds."
    )

class AzureTextGenerator(TextGenerator):
    """
    A TextGenerator for interacting with Azure OpenAI models.

    This class handles client initialization, text generation requests with support for
    system instructions and JSON response schemas, token counting, and resilient
    retries.
    """

    def __init__(self, model_name: str, api_version: str="2025-06-01-preview"):
        """
        Initializes the Azure OpenAI client.

        Args:
            model_name (str): The deployment name of the model in Azure.
            api_version (str): The API version to use (default is "2025-01-01-preview").
        """
        self.model_name = model_name
        self.api_version = api_version
        # try:
        #     # dynamically construct environment variable name for the endpoint based on the model name
        #     endpoint_env_var = f"AZURE_OPENAI_ENDPOINT_{model_name.upper().replace('-', '_').replace('.', '_')}"
        #     azure_endpoint = os.getenv(endpoint_env_var)

        #     if not azure_endpoint:
        #         raise ValueError(f"Environment variable {endpoint_env_var} not set.")

        #     self.client = AzureOpenAI(
        #         api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        #         api_version=self.api_version,
        #         azure_endpoint=azure_endpoint,
        #     )
        #     # This is a quick test to ensure the credentials and endpoint are valid.
        #     self.client.models.list()
        #     logger.info(f"AzureOpenAI client initialized for model: {self.model_name}")

        # except Exception as e:
        #     error_details = format_error(ErrorMessages.TextGeneration.OPENAI_CONNECTION, e)
        #     raise APILogicError(error_details)

    def _get_token_count(self, usage_metadata, task_str: str = None) -> dict:
        """
        Extracts token counts from the Azure OpenAI response's usage object.
        The openai library returns an object with attributes, not a dictionary.
        """
        token_counts = {}
        token_counts_found = False

        if usage_metadata:
            final_log_str = f"MODEL: {self.model_name}."
            if task_str:
                final_log_str += f" TASK: {task_str}."

            token_log_str = " TOKENS:"
        
            for token_type in vr.AZURE_TOKEN_COUNTS_OF_INTEREST:
                token_count = getattr(usage_metadata, token_type, None)
                # handle token tokens so that it matches the Vertex key
                # messy patch, but want to preserve vertex functionality as this is used in production
                # and this isn't
                if token_type == "total_tokens":
                    token_key = app_vr.total_token_count_key
                else:
                    token_key = token_type
                if token_count is not None:
                    token_counts_found = True
                    token_counts[token_key] = token_count
                    token_log_str += f" {token_key}: {token_count}."

        if not token_counts_found:
            logger.warning(f"NO TOKEN COUNTS: When looking through the usage metadata, none of the expected token counts were found ({vr.AZURE_TOKEN_COUNTS_OF_INTEREST})")
            logger.info(final_log_str)
            return None
        else:
            final_log_str += token_log_str
            logger.info(final_log_str)
            return token_counts

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=0.5, max=5),
        before_sleep=log_retry,
        reraise=True
    )
    def generate_text(
        self,
        contents: str,
        system_instruction: str = None,
        response_model: Optional[Type[BaseModel]] = None,
        task_str: str = None
    ) -> dict:
        """
        Makes a request to the Azure OpenAI model using the Responses API.
        Supports both structured (Pydantic) and unstructured outputs.
        """
        pass
        # try:
        #     input_payload = []

        #     # System instruction (if provided)
        #     if system_instruction:
        #         input_payload.append({
        #             "role": "system",
        #             "content": system_instruction
        #         })

        #     # User content
        #     input_payload.append({
        #         "role": "user",
        #         "content": contents
        #     })

        #     # STRUCTURED OUTPUT (Pydantic)
        #     if response_model:
        #         response = self.client.responses.parse(
        #             model=self.model_name,
        #             input=input_payload,
        #             response_format=response_model
        #         )

        #         generated_content = response.output_parsed.model_dump()

        #     # UNSTRUCTURED OUTPUT
        #     else:
        #         response = self.client.responses.create(
        #             model=self.model_name,
        #             input=input_payload
        #         )

        #         generated_content = response.output_text

        #     logger.info("Content generated.")

        #     token_usage = getattr(response, "usage", None)
        #     token_count = self._get_token_count(token_usage, task_str)

        #     return {
        #         app_vr.generated_content_key: generated_content,
        #         app_vr.token_key: token_count
        #     }

        # except Exception as e:
        #     error_details = format_error(
        #         ErrorMessages.TextGeneration.TEXT_GENERATION, e
        #     )
        #     raise APILogicError(error_details)