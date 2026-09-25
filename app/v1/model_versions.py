import variables as vr
from app.common.schemas import LLMProvider

AZURE_PROVIDER_IDENTIFIER = LLMProvider.azure.value
VERTEX_PROVIDER_IDENTIFIER = LLMProvider.vertex.value

MODEL_MAP = {
    AZURE_PROVIDER_IDENTIFIER: {
        "default": "o4-mini",
        vr.haiku_prompt_name: "o4-mini"
    },
    VERTEX_PROVIDER_IDENTIFIER: {
        "default": "gemini-2.5-flash",
        vr.haiku_prompt_name: "gemini-2.5-pro"
    }
}

def create_model_string_for_route(prompts: set) -> str:
    """
    Utility function to get the model string for a route based on the prompts it uses.
    """
    filtered_model_map = {task: model for task, model in MODEL_MAP[VERTEX_PROVIDER_IDENTIFIER].items() if task in prompts}
    s = ""
    for key, val in filtered_model_map.items():
        s += f"{key}:{val}_"
    return s.strip("_")

BIRTHDAY_HAIKU_MODEL_STRING = create_model_string_for_route({vr.haiku_prompt_name})
