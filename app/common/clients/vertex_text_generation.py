#### TEXT GENERATION ####
# Author: Bethany Schoen
# Date: 24th July 2025
##########################
# To communicate with an 
# LLM and generate content
##########################

from google.genai import types, Client
import json
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, RetryCallState
from pydantic import BaseModel
from typing import Optional, Type, Dict, Any

from app.common.clients.text_generation import TextGenerator
import app.common.clients.variables as vr
from app.common.exceptions import ErrorMessages, APILogicError, format_error
import variables as app_vr
from log import logger

load_dotenv(app_vr.gcp_env_file)

def log_retry(retry_state: RetryCallState):
    logger.warning(
        f"Retrying {retry_state.fn.__name__} due to {retry_state.outcome.exception()}. "
        f"Attempt {retry_state.attempt_number} will wait {retry_state.next_action.sleep} seconds."
    )

class VertexTextGenerator(TextGenerator):

    def __init__(self, model_name: str = app_vr.vertex_model_name, api_version: str = "v1"):
        self.model_name = model_name
        self.api_version = api_version
        try:
            # stable API is v1, necessary connection info is in env file
            self.client = Client(http_options=types.HttpOptions(api_version=self.api_version))
        except Exception as e:
            error_details = format_error(ErrorMessages.TextGeneration.GCP_CONNECTION, e)
            raise APILogicError(error_details)
        
    def _get_token_count(self, usage_metadata, task_str: str=None):
        """
        Having made a request to a model, report the token counts (if the keys exist)
        """
        final_log_str = f"MODEL: {self.model_name}." 
        if task_str:
            final_log_str += f" TASK: {task_str}."

        token_log_str = " TOKENS:"
        # https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/list-token#get_the_token_count_of_a_prompt
        # https://googleapis.github.io/python-genai/genai.html#genai.types.GenerateContentResponseUsageMetadata
        
        token_counts = {}
        token_counts_found = False
        for token_type in vr.VERTEX_TOKEN_COUNTS_OF_INTEREST:
            token_count = getattr(usage_metadata, token_type, None)
            if token_count is not None:
                token_counts_found = True
                token_counts[token_type] = token_count
                token_log_str += f" {token_type}: {token_count}."

        if not token_counts_found:
            logger.warning(f"NO TOKEN COUNTS: when looking through the usage metadata, none of the expected token counts were found ({vr.VERTEX_TOKEN_COUNTS_OF_INTEREST})")
            logger.info(final_log_str)
            return None
        else:
            final_log_str += token_log_str
            logger.info(final_log_str)
            return token_counts

    def _pydantic_to_vertex_schema(self, schema_model: Type[BaseModel]) -> types.Schema:
        """
        Converts a Pydantic model into a google.generativeai.types.Schema object.

        This function serves as a wrapper around a recursive helper function.

        Parameters
        ----------
        schema_model : Type[BaseModel]
        A Pydantic model class representing the schema.

        Returns
        -------
        types.Schema
        A google.genai.types.Schema object representing the schema.
        """

        # This mapping is used by the recursive helper function
        JSON_TO_GOOGLE_TYPE_MAP = {
            "string": types.Type.STRING,
            "number": types.Type.NUMBER,
            "integer": types.Type.INTEGER,
            "boolean": types.Type.BOOLEAN,
            "object": types.Type.OBJECT,
            "array": types.Type.ARRAY,
        }

        def _dict_to_schema(schema_dict: Dict[str, Any]) -> types.Schema:
            """
            Recursively converts a JSON schema dictionary into a google.generativeai.types.Schema object.
            """
            if "anyOf" in schema_dict:
                # This handles Optional[T] which Pydantic renders as anyOf: [{type: T}, {type: 'null'}]
                # We find the non-null schema and process it, preserving other keys like 'description'.
                non_null_schemas = [s for s in schema_dict["anyOf"] if s.get("type") != "null"]

                # For a simple Optional, there should be exactly one non-null schema.
                if len(non_null_schemas) == 1:
                    # Create a new schema dict that merges the original's metadata
                    # with the specific type info from the non-null part.
                    new_schema_dict = schema_dict.copy()
                    del new_schema_dict["anyOf"]
                    new_schema_dict.update(non_null_schemas[0])
                    
                    # Recursively call this function with the flattened, corrected schema.
                    return _dict_to_schema(new_schema_dict)

            schema_type_str = schema_dict.get("type")
            if not schema_type_str:
                # Handle cases with '$ref' for nested models, which Pydantic v2 uses.
                if "$ref" in schema_dict:
                    ref_path = schema_dict["$ref"].split('/')
                    ref_name = ref_path[-1]
                    # Pydantic v2 places definitions in '$defs' at the top level of the root schema.
                    # The root schema is passed implicitly through closure.
                    return _dict_to_schema(root_schema['$defs'][ref_name])
                else:
                    raise ValueError("Schema dictionary must have a 'type' or '$ref' key.")

            google_type = JSON_TO_GOOGLE_TYPE_MAP.get(schema_type_str)
            if not google_type:
                raise ValueError(f"Unsupported schema type: {schema_type_str}")

            # Prepare arguments for the types.Schema constructor
            kwargs = {'description': schema_dict.get('description')}

            # Handle object properties recursively
            if google_type == types.Type.OBJECT and "properties" in schema_dict:
                kwargs['properties'] = {
                    key: _dict_to_schema(prop_schema) # RECURSIVE CALL to the helper
                    for key, prop_schema in schema_dict.get("properties", {}).items()
                }
                if "required" in schema_dict:
                    kwargs['required'] = schema_dict["required"]

            # Handle array items recursively
            elif google_type == types.Type.ARRAY and "items" in schema_dict:
                kwargs['items'] = _dict_to_schema(schema_dict["items"]) # RECURSIVE CALL to the helper

            # Handle enums for strings
            if "enum" in schema_dict:
                kwargs['enum'] = schema_dict["enum"]

            # Handle patterns for strings
            if "pattern" in schema_dict:
                kwargs['pattern'] = schema_dict["pattern"]
                
            # Clean up None values before creating the schema object
            final_kwargs = {k: v for k, v in kwargs.items() if v is not None}

            return types.Schema(type=google_type, **final_kwargs)

        # 1. Convert the top-level Pydantic model to a JSON schema dictionary
        root_schema = schema_model.model_json_schema()
        
        # 2. Start the recursive conversion from the root of the JSON schema
        return _dict_to_schema(root_schema)

    def _parse_response(self, response, response_model: Optional[Type[BaseModel]] = None):
        """
        Parses the model's response according to the provided Pydantic model.
        If no model is provided, returns the raw text.

        Parameters
        ----------
        response : types.GenerateContentResponse
            The raw response from the model.
        response_model : Optional[Type[BaseModel]]
            An optional Pydantic model to parse the response into.

        Returns
        -------
        dict or str
            The parsed response as a dictionary if a model is provided, otherwise the raw text.
        """
        if response_model:
            try:
                # get the raw text
                structured_content = response.candidates[0].content.parts[0].text
                # Parse the JSON string into a dictionary
                parsed_content = json.loads(structured_content)
                # Validate and parse the dictionary using the provided Pydantic model
                return response_model.model_validate(parsed_content).model_dump()
            except Exception as e:
                error_details = format_error(ErrorMessages.TextGeneration.RESPONSE_PARSING, e)
                raise APILogicError(error_details)
        else:
            return response.text

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=0.5, max=5),
        before_sleep=log_retry,
        reraise=True
    )
    def generate_text(
        self, 
        contents: str, 
        system_instruction: str=None, 
        response_model: Optional[Type[BaseModel]]=None,
        # use `task_str` instead of the prompt name that was used to setup the generator as generators are cached and the same generator may be used for multiple prompts
        task_str: str=None,
        temperature: float = 0.0
    ) -> dict:
        """
        Makes a request to the text generation model with the provided content, system instruction, and response schema.
        Parameters
        ----------
        contents : str
            The main content or prompt to be sent to the model.
        system_instruction : str, optional
            An optional system instruction to guide the model's behavior.
        response_model : Type[BaseModel], optional
            An optional Pydantic model to structure the model's response.
        task_str : str, optional
            An optional string describing the task, used for logging purposes.

        Returns
        -------
        dict
            A dictionary containing the generated content and token usage.
        """
        try:
            config = types.GenerateContentConfig()
            config.temperature = temperature
            if system_instruction:
                config.system_instruction = system_instruction
            response_schema = None
            if response_model:
                response_schema = self._pydantic_to_vertex_schema(response_model)
                config.response_schema = response_schema
                config.response_mime_type = "application/json"

            response = self.client.models.generate_content(
                model=self.model_name,
                config=config, # if system_instruction or response_model else None, (no longer conditional as temperature is always specified)
                contents=contents
            )

            generated_content = self._parse_response(response, response_model)

            logger.info("Content generated.")
            token_count = self._get_token_count(response.usage_metadata, task_str)

            result = {
                app_vr.generated_content_key: generated_content,
                app_vr.token_key: token_count
            }
            return result
        
        except Exception as e:
            error_details = format_error(ErrorMessages.TextGeneration.TEXT_GENERATION, e)
            raise APILogicError(error_details)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    system_instruction = "You are great at writing Haikus about Pokemon. You'll be given a Pokemon's name and you will write a Haiku about it."

    ## GCP application  
    gcp_content = "Charmander"
    tg = VertexTextGenerator()
    result = tg.generate_text(gcp_content, system_instruction=system_instruction, task_str="Haiku demo")

    haiku = result[app_vr.generated_content_key]
    tokens = result[app_vr.token_key]
    print(haiku)
    print("TOKENS: ", tokens)