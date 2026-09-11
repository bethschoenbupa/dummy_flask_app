# to check the structure of requests are correct
from pydantic import validate_call
from typing import Callable
import json

# service-specific utils
from app.v1.utils.birthday_haiku import is_birthday, generate_birthday_haiku

# prompt retrieval used by all services
import app.v1.prompt_versions as pv
from app.common.utils.prompt_retrieval import get_prompt
# request and response models for all services
from app.v1.schemas import HaikuRequestModel, HaikuResponseModel, HaikuServiceResult
from app.common.schemas import Metadata
import app.common.clients.response_schemas as rs

from app.common.clients.text_generation import TextGenerator

from log import logger
import variables as vr

@validate_call
def haiku_service(
    validated_data: HaikuRequestModel,
    get_generator: Callable[[str], TextGenerator], 
    prompt_map: dict=pv.HAIKU_PROMPT_MAP
) -> HaikuServiceResult:
    """
    Service to generate a birthday haiku based on user input.
    """
    # 0. Check prompt data - if anything is missing, we'll use the default version in `prompt_versions.py`
    # create a copy of the prompt_map to avoid modifying the original dictionary
    prompt_map = dict(prompt_map)
    for prompt in pv.HAIKU_PROMPT_MAP:
        if prompt not in prompt_map:
            # use default version if not provided in prompt_map
            logger.warning(f"Prompt {prompt} not found in provided prompt_map, using default version from HAIKU_PROMPT_MAP")
            prompt_map[prompt] = pv.HAIKU_PROMPT_MAP[prompt]
    
    # 1. Check if today is the user's birthday
    birthday_today = is_birthday(validated_data.date)
    
    # 2. Get the haiku-writing prompt
    prompt = get_prompt(prompt_name=vr.haiku_prompt_name, version=prompt_map[vr.haiku_prompt_name])

    # 3. Use an LLM to write the prompt
    result = generate_birthday_haiku(
        name=validated_data.name,
        is_birthday=birthday_today,
        prompt=prompt,
        get_generator=get_generator
    )
    haiku = result[rs.HAIKU_KEY]
    tokens = result[vr.token_key]
    models = result[vr.models_key]

    # 4. Generate the response
    response = HaikuServiceResult(
        data=HaikuResponseModel(
            is_birthday=birthday_today,
            haiku=haiku
        ),
        metadata=Metadata(
            model=json.dumps(models),
            prompts={vr.haiku_prompt_version_key: prompt_map[vr.haiku_prompt_name]},
            tokens=tokens
        )
    )

    return response

# ================================= #
#      --- Next Year Service ---    #
# ================================= #

# Paste notebook code here