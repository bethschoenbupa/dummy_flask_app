from google import genai
from google.genai import types
import json
from dotenv import load_dotenv

load_dotenv(".env.public")

class TextGenerationGCP:

    def __init__(self, model_name: str = "gemini-2.5-flash", api_version: str = "v1"):
        self.model_name = model_name
        self.api_version = api_version
        # stable API is v1, necessary connection info is in env vile
        self.client = genai.Client(http_options=types.HttpOptions(api_version=self.api_version))

    def generate_text(self, contents: str, system_instruction: str=None, response_schema: dict=None):
        try:
            config = types.GenerateContentConfig()
            if system_instruction:
                config.system_instruction = system_instruction
            if response_schema:
                config.response_schema = response_schema
                config.response_mime_type = "application/json"

            response = self.client.models.generate_content(
                model=self.model_name,
                config=config if system_instruction or response_schema else None,
                contents=contents
            )

            if response_schema:
                generated_content = json.loads(response.candidates[0].content.parts[0].text)
            else:
                generated_content = response.text

            return generated_content
        
        except Exception as e:
            error = "Something went wrong when trying to generate text: "
            print(error)
            raise e