import datetime
from flask import jsonify, request, g, Response, current_app
from flask_limiter.errors import RateLimitExceeded
from pydantic import ValidationError
from werkzeug.exceptions import BadRequest, UnsupportedMediaType
import uuid
import json
from typing import Union

from app.common.schemas import ErrorData
from app.common.exceptions import ErrorMessages, APILogicError, format_error, ErrorDetail
from pydantic import ValidationError
from app.v1.schemas import InferenceMetadata, ApiResponse

def _build_error_response_body(
    error_data: ErrorData
) -> ApiResponse:
    """
    Builds the appropriate error response Pydantic model based on the request type
    Parameters
    ----------
    error_data : ErrorData
        The error to be reported

    Returns
    -------
    ApiResponse
        The structured response to be reported
    """
    
    inference_metadata = InferenceMetadata(
        request_id=g.request_id,
        route=request.path,
        api_version=g.api_version,
        status="ERROR"
    )
    
    return ApiResponse(
        inference_metadata=inference_metadata,
        failures=error_data
    )
    
def _dispatch_response(
    response_body: ApiResponse, 
    http_code: int
):
    """
    Serializes the response body to bytes and determines the content type
    Parameters
    ----------
    response_body : ApiResponse
        The response to be reported - created using _build_error_response_body
    http_code : int
        The http code to return with the response

    Returns
    -------
    Response
        The Flask response object
    """
    error_body_dict = response_body.model_dump(by_alias=True)
    
    payload_bytes = json.dumps(error_body_dict).encode('utf-8')
    content_type = 'application/json'

    return Response(payload_bytes, status=http_code, mimetype=content_type)
    
def handle_error(
    error_details: dict
) -> Response:
    """
    Handle an error by logging it and returning a JSON response
    Orchestrates building, serializing, and dispatching the error
    Parameters
    ----------
    request_logger : RequestLogger
        Information regarding the request
    error_details : dict
        The error details, including code, http_code, msg, and error
        
    Returns
    -------
    Response
        The Flask response
    """
    # Validate structure of error data before continuing
    validated_error_details = ErrorDetail(**error_details)

    # 1. Create the ErrorData object
    print(f"Handling error: {error_details['error']}")
    error_data = ErrorData(
        code=validated_error_details.code,
        http_code=validated_error_details.http_code,
        error_title=validated_error_details.msg,
        detail=validated_error_details.error
    )

    # 2. Build the core response object
    response_body = _build_error_response_body(error_data)

    # 3. Serialize the response object into bytes and dispatch
    return _dispatch_response(response_body, validated_error_details.http_code)
    

def register_error_handlers(app):
    """
    Registers all custom error handlers for the Flask app.
    This function should be called only ONCE during app creation.
    """

    @app.errorhandler(APILogicError)
    def handle_api_logic_error(e):        
        return handle_error(e.error_details)

    @app.errorhandler(ValidationError)
    def handle_request_validation_error(e: ValidationError):
        """
        Handles validation errors from incoming requests.
        Returns a 422 Unprocessable Entity response.
        """        
        # Inspect the error details
        for err in e.errors():
            # specific validation error
            if err['type'] == 'value_error':
                error_details = format_error(ErrorMessages.App.INCORRECT_VALUE, e)
            # other validation error
            else:
                error_details = format_error(ErrorMessages.App.MISSING_INFO, e)
        
        return handle_error(error_details)

    @app.errorhandler(Exception)
    def handle_generic_error(e):
        print(f"An unexpected error occurred: {e}", exc_info=True)
        generic_error = format_error(ErrorMessages.App.UNEXPECTED_ERROR, str(e))
        return handle_error(generic_error)