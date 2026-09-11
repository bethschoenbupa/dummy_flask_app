from abc import ABC, abstractmethod

class TextGenerator(ABC):
  """
  Defines the interface, to be used by the services/utils
  """

  @abstractmethod
  def generate_text(
    self,
    contents: str,
    system_instruction: str = None,
    response_schema: dict = None,
    task_str: str = None
  ) -> dict:
    raise NotImplementedError