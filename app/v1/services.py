# to check the structure of requests are correct
from pydantic import validate_call

# service-specific utils
from app.v1.utils.birthday_haiku import is_birthday, generate_birthday_haiku

# prompt retrieval used by all services
from app.common.utils.prompt_retrieval import get_prompt
# request and response models for all services
from app.v1.schemas import HaikuRequestModel, HaikuResponseModel, HaikuServiceResult

@validate_call
def haiku_service(request: HaikuRequestModel) -> HaikuServiceResult:
    """
    Service to generate a birthday haiku based on user input.
    """
    
    # 1. Check if today is the user's birthday
    birthday_today = is_birthday(request.date)
    
    # 2. Get the haiku-writing prompt
    # (we could store the name and version in a separate file as constants)
    # (this would make it easier to update in the future)
    prompt = get_prompt(prompt_name="birthday_haiku", version="latest")

    # 3. Use an LLM to write the prompt
    haiku = generate_birthday_haiku(
        name=request.name,
        is_birthday=birthday_today,
        prompt=prompt
    )

    # 4. Generate the response
    haiku_result = HaikuResponseModel(
        is_birthday=birthday_today,
        haiku=haiku
    )

    response = HaikuServiceResult(
        data=haiku_result
    )

    return response

# ================================= #
#      --- Next Year Service ---    #
# ================================= #

# Paste notebook code here