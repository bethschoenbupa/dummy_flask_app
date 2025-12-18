from datetime import datetime

from app.common.utils.text_generation import TextGeneration

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
    prompt: str
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

    tg = TextGeneration()
    birthday_haiku = tg.generate_text(messages)

    return birthday_haiku