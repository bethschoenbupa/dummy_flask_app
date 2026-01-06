## BLUA FAMILY FLASK API ##
# Author: Bethany Schoen
# Date: 17th December 2025
############################
# Decorator for common logic
# in flask routes
############################

from functools import wraps
from flask import request, Response, g
import json

from app.v1.schemas import InferenceMetadata, ApiResponse

# this function creates the decorator and is run at python start-up time
# it allows the decorator to accept arguments (otherwise wouldn't be needed)
def api_route(
    http_request_model, 
    service_result_model
):
    """
    A decorator to standardize API route handling.
    - Validates request against a Pydantic model.
    - Calls the decorated function (the service logic) with validated data.
    - Constructs a standardised success response envelope.
    """
    # -- if any code was here, it would run at import time and run only once --

    # this function receives the function being wrapped and wraps it
    # it replaces the OG function with the wrapped function
    def decorator(service_func):
        @wraps(service_func)
        # This is the new logic before and after the wrapped function and runs when requested
        def wrapper(*args, **kwargs):
            
            # 1. Get request data
            input_dict = request.get_json(silent=True)     
            
            # 2. Validate input 
            validated_input = http_request_model(**input_dict)
            
            # 3. Delegate all logic to the service function
            service_result = service_func(validated_input)            
            # Enforce the contract: the return value MUST conform to the ServiceResult model
            validated_service_result = service_result_model.model_validate(service_result)
            
            # 4. Construct the standard success response
            data = validated_service_result.data

            inference_metadata = InferenceMetadata(
                request_id=g.request_id,
                route=request.path,
                api_version=g.api_version,
                status="SUCCESS"
            )

            TypedApiResponse = ApiResponse[type(data)]
            response_body = TypedApiResponse(
                result=data,
                inference_metadata=inference_metadata
            )
            response_body_obj = response_body.model_dump(by_alias=True)

            # 5. Return  
            payload_bytes = json.dumps(response_body_obj).encode('utf-8')
            content_type = 'application/json'
            
            return Response(payload_bytes, status=200, mimetype=content_type)
        
        return wrapper
    return decorator