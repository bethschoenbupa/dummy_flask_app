import variables as vr

haiku_prompt_version = 1

HAIKU_PROMPT_MAP = {
    vr.haiku_prompt_name: haiku_prompt_version
}

def create_prompt_string_for_route(prompts: set) -> str:
    """
    Utility function to get the prompt version string for a route based on the prompts it uses.
    """
    s = ""
    for key, val in prompts.items():
        s += f"{key}:{val}_"
    return s.strip("_")

BIRTHDAY_HAIKU_PROMPT_VERSION_STRING = create_prompt_string_for_route(HAIKU_PROMPT_MAP)