## BLUA FAMILY FLASK API ##
# Author: Bethany Schoen
# Date: 17th December 2025
############################
# Decorator for common logic
# in flask routes
############################

from functools import wraps
from flask import Request, request, Response, g, current_app
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Type, Callable
from pydantic import BaseModel, ValidationError

from app.common.schemas import AIRequestContext
from app.common.clients.text_generator_factory import TextGeneratorFactory
from app.v1.schemas import InferenceMetadata, ApiResponse, Status
from app.v1.model_versions import MODEL_MAP

from app.common.exceptions import (
    APILogicError, 
    ErrorMessages,
    RequestValidationError, 
    format_error
)

from log import logger
import variables as vr

@dataclass
class ParsedRequestContext:
    """A structured object to hold information parsed from the request."""
    body: Dict[str, Any]
    provider: str = "vertex"
    shadow_mode: bool = False
    error: str = None

# --- 1. Parse HTTP request into structured context ---

def parse_http_request(req: Request) -> ParsedRequestContext:
    """
    Parses a direct HTTP request (JSON).
    Parameters
    ----------
    req : Request
        Flask object with all request data

    Returns
    -------
    ParsedRequestContext
        extracted request data used throughout by the route decorator
    """
    # instantiate context to include default values
    context = ParsedRequestContext(
        # parameters extracted from the request
        provider="vertex",
        shadow_mode=False,
        body={},
        # this is updated only if something goes wrong
        error=None
    )

    request_headers = req.headers
    # 1. Provider (taken from the headers, default to vertex)
    context.provider = request_headers.get("X-LLM-Provider", "vertex")
    # 2. Shadow mode (taken from the headers, but only enabled if the config allows it)
    context.shadow_mode = request_headers.get("X-Shadow-Mode", "false").lower() == "true" and current_app.config.get('ALLOW_SHADOW_TRAFFIC', False)

    # 3. Request body (data to be processed by the service)
    if req.is_json:
        # Use get_json() without silent=True to handle empty body
        request_data = req.get_json(silent=True)
        if request_data is None: 
            context.error = "Request body is empty or not valid JSON."
        else:
            context.body = request_data
    else:
        context.error = "Unsupported Content-Type. Expected 'application/json'."

    return context

# --- 2. Input Validation Helper ---

def validate_request_data(
    input_dict: Dict[str, Any],
    json_request_model: Type[BaseModel],
) -> BaseModel:
    """
    Validates the input dictionary against the appropriate Pydantic model.
    Parameters
    ----------
    input_dict : Dict[str, Any]
        Data extracted from the request to be processed by the service
    json_request_model : Type[BaseModel]
        Pydantic model specifying expected structure of input_dict (for json requests)

    Returns
    -------
    BaseModel
        The input data reconstructed using the correct request model

    Raises
    ------
    RequestValidationError
        If the input data does not match the expected structure
    """
    try:
        if not isinstance(input_dict, dict):
            error_detail = [{
                'loc': ('body',), 
                'msg': 'Request body must be a JSON object.', 
                'type': 'missing'
            }]
            raise RequestValidationError.from_exception_data(
                title=json_request_model.__name__,
                line_errors=error_detail
            )
        validated_input = json_request_model(**input_dict)
        return validated_input
    except ValidationError as e:
        # Re-raise as a standardized application error
        raise RequestValidationError.from_exception_data(
            title=e.title,
            line_errors=e.errors(),
        ) from e

# --- 3. Service Logic Execution Helper ---

def execute_service_logic(
    service_func: Callable,
    validated_input: BaseModel,
    service_result_model: Type[BaseModel],
    context: ParsedRequestContext
) -> BaseModel:
    """
    Executes the core service function and validates its result.
    Parameters
    ----------
    service_func : Callable
        Business logic function performing transformation on the input data
    validated_input : BaseModel
        Input data from the request whose structure has been validated
    service_result_model : Type[BaseModel]
        Expected data structure (Pydantic model) from the service function
    context : ParsedRequestContext
        extracted request data that includes provider and shadow mode info (for the text gen factory)

    Returns
    -------
    BaseModel
        The result from the service function, validated to ensure it has returned the expected structure

    Raises
    ------
    APILogicError
        The response from the service fails validation
    """
    ai_context = AIRequestContext(provider=context.provider, shadow_mode=context.shadow_mode)
    generator_factory = TextGeneratorFactory(ai_context=ai_context, model_map=MODEL_MAP)

    service_result = service_func(validated_input, generator_factory.get_generator)

    try:
        # Enforce the contract: the return value MUST conform to the ServiceResult model
        return service_result_model.model_validate(service_result)
    except Exception as e:
        error_details = format_error(ErrorMessages.App.BAD_SERVICE_RESPONSE, e)
        raise APILogicError(error_details)

# --- 4. Response Construction Helper ---

def build_api_response(
    validated_service_result: BaseModel
) -> BaseModel:
    """
    Constructs the final ApiResponse model.
    Parameters
    ----------
    validated_service_result : BaseModel
        The response from the business logic layer, to be returned

    Returns
    -------
    BaseModel
        The response, constructed using Pydantic models, to be returned to the API user
    """
    data = validated_service_result.data
    service_metadata = validated_service_result.metadata

    total_tokens = service_metadata.tokens.get(vr.total_token_count_key)
    if total_tokens is None:
        logger.warning(f"NO TOTAL TOKENS: when looking through the service metadata tokens, the expected total token count key '{vr.total_token_count_key}' was not found")
        total_tokens = -1  # default value if not found

    inference_metadata = InferenceMetadata(
        request_id=g.request_id,
        api_version=g.api_version,
        status=Status.Success,
        model=service_metadata.model,
        prompts=service_metadata.prompts,
        tokens=total_tokens
    )

    TypedApiResponse = ApiResponse[type(data)]
    return TypedApiResponse(
        result=data,
        inference_metadata=inference_metadata
    )

# --- 5. Response Finalization Helper ---

def finalise_and_send_response(
    response_body: BaseModel,
    partial_result: bool
) -> Response:
    """
    Serialises the response and sends it via HTTP.
      As the structure of `data` can vary by route, we need to log the dumped version.
      This makes sure we don't accidently log a string version.
      Other objects (e.g. service_metadata) are validated and dumped within the request_logger method.
    Parameters
    ----------
    response_body : BaseModel
        The response data to be sent back to the user
    partial_result : bool
        Flag returned by the service to specify whether only a partial result has been created

    Returns
    -------
    Response
        Flask response
    """
    response_body_obj = response_body.model_dump(by_alias=True)
    payload_bytes = json.dumps(response_body_obj).encode('utf-8')
    content_type = 'application/json'

    # Log response data (now that it's serialized)
    g.request_logger.log_response_data(response_body_obj.get("result", {})) 
            
    http_code = 206 if partial_result else 200
    return Response(payload_bytes, status=http_code, mimetype=content_type)

# ---  6. Route Decorator ---

# this function creates the decorator and is run at python start-up time
# it allows the decorator to accept arguments (otherwise wouldn't be needed)
def api_route(
    json_request_model,
    service_result_model
):
    """
    A decorator to standardise API route handling by coordinating parsing,
    validation, execution, and response generation.
    """
    def decorator(service_func):
        @wraps(service_func)
        def wrapper(*args, **kwargs):

            # Other attributes used across the app (e.g. for caching) can be saved in `g`
            g.request_models = [json_request_model]
            g.service_result_model = service_result_model

            # 1. Parse Request & Establish Context
            context = parse_http_request(request)

            # If something went wrong during parsing, context.error will be populated
            if context.error:
                error_details = format_error(ErrorMessages.App.BAD_REQUEST_BODY, context.error)
                raise APILogicError(error_details)
            
            # Store provider and shadow mode in `g` for caching
            g.provider = context.provider
            g.shadow_mode = context.shadow_mode
            
            # Log raw input after parsing
            g.request_logger.log_input_data(context.body)

            # 2. Validate Input
            validated_input = validate_request_data(
                input_dict=context.body,
                json_request_model=json_request_model,
            )

            # 3. Execute Service Logic
            validated_service_result = execute_service_logic(
                service_func=service_func,
                validated_input=validated_input,
                service_result_model=service_result_model,
                context=context
            )
            # Log service-level metadata
            g.request_logger.log_response_metadata(validated_service_result.metadata)

            # 4. Construct the API Response Body
            response_model = build_api_response(
                validated_service_result=validated_service_result
            )

            # 5. Serialise and Send Response (response is also logged in this function)
            return finalise_and_send_response(
                response_body=response_model,
                partial_result=validated_service_result.partial_result
            )

        return wrapper
    return decorator