from datetime import datetime
from typing import Callable
import json

from app.common.clients.response_schemas import HaikuResponse, HAIKU_KEY
from app.common.clients.text_generation import TextGenerator

from app.common.exceptions import ErrorMessages, APILogicError, format_error
import variables as vr

def is_birthday(birthday: datetime):
    """
    Check if today is the user's birthday.
    Parameters
    ----------
    birthday : datetime
        The user's birthday.
    Returns
    -------
    bool
        True if today is the user's birthday, False otherwise.
    """

    if not isinstance(birthday, datetime):
        try:
            birthday_datetime = datetime.strptime(birthday, "%Y-%m-%d")
        except:
            raise Exception("Not correct date format")
        
    elif isinstance(birthday, datetime):
        birthday_datetime = birthday

    else:
        raise Exception("Inputted birthday is not recognised.")

    today = datetime.today()

    if (today.month == birthday_datetime.month) & (today.day == birthday_datetime.day):
        return True
    else:
        return False
    
def generate_birthday_haiku(
    name: str,
    is_birthday: bool,
    prompt: str,
    get_generator: Callable[[str], TextGenerator]
):
    """
    Generate a birthday haiku using an LLM.
    1. Prepare the user information in JSON format.
    2. Construct the messages for the LLM.
    3. Call the LLM with the user information and prompt.
    4. Return the haiku.

    Parameters
    ----------
    name : str
        The name of the person.
    is_birthday : bool
        Whether today is their birthday.
    prompt : str
        The prompt to use for the LLM.
    Returns
    -------
    str
        The generated haiku.
    """
    user_info = {
        "name": name,
        "is_birthday": is_birthday
    }

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": str(user_info)}
    ]

    haiku_generator = get_generator(task=vr.haiku_prompt_name)
    text_gen_result = haiku_generator.generate_text(
        json.dumps(user_info), 
        system_instruction=prompt, 
        response_model=HaikuResponse,
        task_str=vr.haiku_task_str
    )

    if vr.generated_content_key not in text_gen_result or vr.token_key not in text_gen_result:
        error_details = format_error(ErrorMessages.TextGeneration.INCORRECT_RESPONSE_FORMAT)
        raise APILogicError(error_details)

    haiku = text_gen_result[vr.generated_content_key][HAIKU_KEY]
    tokens = text_gen_result[vr.token_key]

    try:
        result = {
            HAIKU_KEY:haiku,
            vr.token_key:tokens,
            vr.models_key: {
                vr.haiku_prompt_name: haiku_generator.model_name
            }
        }
    # result doesn't have expected keys - response format has not been conformed to
    except Exception as e:
        error_details = format_error(ErrorMessages.BirthdayHaiku.INCORRECT_RESPONSE_FORMAT, e)
        raise APILogicError(error_details)

    return result