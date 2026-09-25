####### EXCEPTIONS #######
# Author: Bethany Schoen
# Date: 17th December 2025
###########################
# Define anticipated errors
###########################

from pydantic import ValidationError, BaseModel, validate_call
from functools import wraps

# the structure of one error message
class ErrorDetail(BaseModel):
    msg: str
    error: str
    code: int
    http_code: int=400

# a collection of error messages for the application
class ErrorMessages:

    class App:
        MISSING_INFO = ErrorDetail(
            msg="Invalid input",
            error="Information is missing from the body of your request. Please refer to the API documentation.",
            code=1001,
            http_code=422
        )
        INCORRECT_VALUE = ErrorDetail(
            msg="One or more of your request elements are invalid",
            # error should be created by pydantic model
            error="",
            code=1002,
            http_code=422
        )
        CATEGORIES_UNRECOGNISED = ErrorDetail(
            msg="Categories for classification are not recognised",
            error="Categories {} unknown",
            code=1003
        )
        DATE_DATA_TYPE = ErrorDetail(
            msg="Datatype of variable 'date' not recognised",
            error="Datatype of 'date' must be 'str'",
            code=1004
        )
        DATE_CONVERSION = ErrorDetail(
            msg="Date format invalid",
            error="Unable to convert date input. Make sure it's a string in the format '%Y-%m-%d'",
            code=1005
        )
        TIME_OF_DAY_UNRECOGNISED = ErrorDetail(
            msg="Time of day input invalid",
            error="For timeOfDay, expected one of {}, received '{}'",
            code=1006
        )
        EMPTY_LIST_INPUT = ErrorDetail(
            msg="One of the lists you've inputted is empty",
            error="You can't send us empty lists...",
            code=1007
        )
        RATE_LIMIT_EXCEEDED = ErrorDetail(
            msg="Rate limit exceeded",
            error="You've made too many requests. Wait a minute...",
            code=1008,
            # limit exceeded
            http_code=429
        )
        TRENDS_UNRECOGNISED = ErrorDetail(
            msg="Trends input invalid",
            error="For trends, expected one of {}, received '{}'",
            code=1009
        )
        BAD_REQUEST_BODY = ErrorDetail(
            msg="Unable to parse request body",
            error="Request body is missing or content-type is not application/json",
            code=1010
        )
        BAD_SERVICE_RESPONSE = ErrorDetail(
            msg="The service function returned an invalid object. It must return an instance of a ServiceResult model",
            error="",
            code=1011,
            http_code=500
        )
        INTERNAL_VALIDATION_ERROR = ErrorDetail(
            msg="An internal function was called with invalid parameters",
            error="",
            code=1012,
            # internal server error
            http_code=500
        )
        PUBSUB_PUBLISH_FAILURE = ErrorDetail(
            msg="Unable to publish response",
            error="",
            code=1012,
            # internal server error
            http_code=500
        )
        MISSING_RESPONSE_SCHEMA = ErrorDetail(
            msg="Missing response schema",
            error="An Avro response has been requested, but the response schema hasn't been provided.",
            code=1013,
            http_code=500
        )
        BAD_PROMPT_MAP = ErrorDetail(
            msg="Prompt map is missing information",
            error="The keys within the prompt map don't match the expected prompt names. Check that the prompt map is correctly structured and includes all necessary keys.",
            code=1014,
            http_code=500
        )
        UNEXPECTED_ERROR = ErrorDetail(
            msg="Something went wrong when trying to parse the request body",
            error="",
            code=1099,
            # internal server error
            http_code=500
        )

    class TextGeneration:
        OPENAI_CONNECTION = ErrorDetail(
            msg="Unable to connect to OpenAI client",
            error="Connection to OpenAI failed",
            code=2001,
            # bad gateway
            http_code=502
        )
        TEXT_GENERATION = ErrorDetail(
            msg="Unable to generate text",
            error="Text generation process failed",
            code=2002,
            # bad gateway
            http_code=502
        )
        CANT_CONSTRUCT_PROMPT = ErrorDetail(
            msg="Can't create messages for LLM",
            error="Necessary information to be included in the prompt is missing",
            code=2003,
            http_code=422
        )
        BAD_MESSAGES = ErrorDetail(
            msg="Incorrect formatting of LLM messages",
            error="LLM messages must be a list of dictionaries",
            code=2004,
            http_code=422
        )
        GCP_CONNECTION = ErrorDetail(
            msg="Unable to connect to Google GenAI client",
            error="Connection to Google failed",
            code=2005,
            # bad gateway
            http_code=502
        )
        INCORRECT_RESPONSE_FORMAT = ErrorDetail(
            msg="Unexpected response from generate_text",
            error=f"Expected a dictionary with keys 'generated_content' and 'tokens'",
            code=2006,
            # semantic error - code worked but response is not what was expected
            http_code=422
        )
        RESPONSE_SCHEMA_UNRECOGNISED = ErrorDetail(
            msg="Unrecognised response schema",
            error="The provided response schema doesn't match any of the schemas we have set up in variables.py",
            code=2007,
            # bad setup
            http_code=500
        )
        NO_PROVIDER = ErrorDetail(
            msg="LLM provider not recognised",
            error="The specified LLM provider is not recognised. Check AIRequestContext and MODEL_MAP.",
            code=2008,
            http_code=500
        )
        NO_MODEL = ErrorDetail(
            msg="Model not configured for task",
            error="No model is configured for the specified task and provider. Check MODEL_MAP.",
            code=2009,
            http_code=500
        )
        NO_MOCK_RESPONSE = ErrorDetail(
            msg="No mock response found for the provided response schema",
            error="The provided response schema doesn't match any of the schemas we have set up in variables.py",
            code=2010,
            # bad setup
            http_code=500
        )
        MOCK_RESPONSE_VALIDATION = ErrorDetail(
            msg="Mock response doesn't match expected schema",
            error="The mock response for this task doesn't match the expected response schema. Check that the mock response in variables.py is correctly structured and includes all necessary keys.",
            code=2011,
            http_code=500
        )
        RESPONSE_PARSING = ErrorDetail(
            msg="Unable to parse LLM response according to the provided schema",
            error="The response from the LLM failed validation against the provided response schema. Check that the response schema is correctly set up and that the LLM is returning all necessary information in the expected format.",
            code=2012,
            http_code=500
        )

    class PromptRetrieval:
        PROMPT_TABLE_NOT_FOUND = ErrorDetail(
            msg="Couldn't connect to prompt table",
            error="Prompt data not found. Please report issue to developers.",
            code=6001,
            http_code=502
        )
        BAD_PROMPT_DATA = ErrorDetail(
            msg="Prompt data missing information",
            error="Prompt name, contents, and/or version are missing from the prompt dataset",
            code=6002,
            http_code=502
        )
        PROMPT_NAME_UNRECOGNISED = ErrorDetail(
            msg="No prompt found",
            error="Filtering conditions returned no data. Prompt name not recognised",
            code=6003,
            # resource not found, but internal error
            http_code=500
        )
        VERSION_UNRECOGNISED = ErrorDetail(
            msg="No prompt found",
            error="Version not recognised. Use 'latest' to retrieve the most recent prompt.",
            code=6004,
            # resource not found, but internal error
            http_code=500
        )
        MULTIPLE_PROMPTS_FOUND = ErrorDetail(
            msg="Multiple prompts found",
            error="Filtering conditiosn returned multiple prompts. Check prompt table.",
            code=6005,
            # conflicting resoure state - shouldn't be returning multiple prompts, this needs to be fixed
            http_code=409
        )
        PROMPT_DATA_NOT_LOADED = ErrorDetail(
            msg="Prompt data not loaded",
            error="Prompt data has not been loaded into the application context during app startup",
            code=6006,
            http_code=500
        )
        CANT_SAVE_NEW_PROMPT = ErrorDetail(
            msg="Unable to save new prompt to prompt dataset",
            error="",
            code=6007,
            http_code=500
        )

    class RequestLogger:
        TYPE_NOT_RECOGNISED = ErrorDetail(
            msg="Log type not recognised",
            error="Expected one of 'input', 'response', or 'error",
            code=7001,
            # issue with code logic 
            http_code=500
        )
        DATA_NOT_FOUND = ErrorDetail(
            msg="Data not found",
            error="The CSV could not be found at the specified path",
            code=7002,
            # issue with code logic 
            http_code=500
        )
        COULDNT_WRITE_DATA = ErrorDetail(
            msg="Couldn't write data",
            error="The CSV could not be written at the specified path",
            code=7003,
            # issue with code logic 
            http_code=500
        )
        INVALID_DATA_FORMAT = ErrorDetail(
            msg="Couldn't write data to CSV",
            error="Expected a pd.DataFrame",
            code=7004,
            # issue with code logic 
            http_code=500
        )
        MISMATCHING_DATA_STRUCTURE = ErrorDetail(
            msg="Couldn't append request to existing log data",
            error="The recorded log data does not match the expected structure",
            code=7004,
            # issue with code logic 
            http_code=500
        )

    class BirthdayHaiku:
        INCORRECT_RESPONSE_FORMAT = ErrorDetail(
            msg="Unexpected response from LLM",
            error=f"Expected a dictionary with keys 'haiku'",
            code=8001,
            # semantic error - code worked but response is not what was expected
            http_code=422
        )


# if an Exception was raised, use this function to format it into a dictionary
def format_error(error_detail, exception=None):
    """
    Append exception details to the error message structure
    Parameters
    ----------
    error_detail: ErrorDetail
        The error to be formatted
    exception: Exception | None
        Any type of exception that has been raised by the application
        If None, the pre-defined error message will be used

    Returns
    -------
    dict
        A dictionary containing the full error details
    """
    error_details = {
        "msg": error_detail.msg,
        "error": str(exception) if exception else error_detail.error,
        "code": error_detail.code,
        "http_code": error_detail.http_code
    }
    return error_details

# a custom exception class for known application errors
class APILogicError(Exception):
    """
    Custom exception for our application's known business logic errors.
    It carries the pre-formatted error dictionary that handle_error() expects.
    """
    def __init__(self, error_details: dict):
        self.error_details = error_details
        # Set the exception message to the user-facing title for easier debugging
        super().__init__(error_details.get("msg", "An API Logic Error occurred."))

class RequestValidationError(ValidationError):
    """
    Custom exception to represent a validation error originating from an
    incoming HTTP request. This should typically result in a 4xx response.
    """
    pass


class InternalValidationError(ValidationError):
    """
    Custom exception to represent a validation error originating from
    internal service-to-util communication. This indicates a bug and
    should typically result in a 500 response.
    """
    pass

def validate_internal_call(func):
    """
    A decorator that wraps Pydantic's `validate_call` to catch its
    ValidationErrors and re-raise them as InternalValidationError.
    This signals a bug in the inter-service communication.
    """
    validated_func = validate_call(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return validated_func(*args, **kwargs)
        except ValidationError as e:
            # An error here means a developer passed the wrong type from
            # one part of our code to another. This is an internal bug.
            raise InternalValidationError.from_exception_data(
                title=func.__name__,
                line_errors=e.errors(),
            ) from e
    
    return wrapper