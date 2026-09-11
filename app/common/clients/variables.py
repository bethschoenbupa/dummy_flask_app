import variables as vr
import app.common.clients.response_schemas as rs
from app.common.schemas import LLMProvider

AZURE_PROVIDER_IDENTIFIER = LLMProvider.azure.value
VERTEX_PROVIDER_IDENTIFIER = LLMProvider.vertex.value

MOCK_HAIKU_RESPONSE = {rs.HAIKU_KEY: "Empty cake awaits\nAlice sighs beneath moonlight\nNo candle to blow."}

TASK_MAP = {
    vr.haiku_task_str: MOCK_HAIKU_RESPONSE,
}

MOCK_MODEL_NAME = "mock_model"
MOCK_PROVIDER_NAME = "mock"

VERTEX_TOKEN_COUNTS_OF_INTEREST = [
    "cached_content_token_count", 
    "candidates_token_count", 
    "prompt_token_count", 
    "thoughts_token_count", 
    "total_token_count"
]

AZURE_TOKEN_COUNTS_OF_INTEREST = [
    "input_tokens", 
    "output_tokens", 
    "total_tokens"
]