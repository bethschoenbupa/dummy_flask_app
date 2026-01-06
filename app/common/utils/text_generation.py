from openai import AzureOpenAI
import os
from dotenv import load_dotenv
load_dotenv()

class TextGeneration:
    """
    Text generation using Azure OpenAI's 4o-mini model.
    ----------
    Parameters
    model : str
        The model to use for text generation. Default is "4o-mini".
    """

    def __init__(self, model: str="4o-mini"):
        self.model = model        
        self.client_4o = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2025-01-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT_4O")
        )

    def generate_text(self, messages: list) -> dict:
        """
        Generate text based on the provided messages.
        ----------
        Parameters
        messages : list
            A list of message dictionaries to send to the model.

        Returns
        -------
        dict
            A dictionary containing the generated text and token usage.
        
        Raises
        -------
        APILogicError
            If there is an error during text generation.
        """
        response = self.client_4o.chat.completions.create(
            model=self.model,
            messages=messages
        )
        generated_text = response.choices[0].message.content

        return generated_text