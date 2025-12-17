####### EXCEPTIONS #######
# Author: Bethany Schoen
# Date: 17th December 2025
###########################
# Define anticipated errors
###########################

from pydantic import BaseModel

# the structure of one error message
class ErrorDetail(BaseModel):
    msg: str
    error: str
    code: int
    http_code: int=400

# a collection of error messages for the application
class ErrorMessages:

    class App:
        DATE_CONVERSION = ErrorDetail(
            msg="Date format invalid",
            error="Unable to convert date input. Make sure it's a string in the format '%Y-%m-%d'",
            code=1001
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