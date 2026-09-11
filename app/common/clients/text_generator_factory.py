import app.common.clients.variables as vr
from app.common.schemas import AIRequestContext, LLMProvider
from app.common.clients.mock_text_generation import MockTextGenerator
from app.common.clients.vertex_text_generation import VertexTextGenerator
from app.common.clients.azure_text_generation import AzureTextGenerator

from app.common.exceptions import ErrorMessages, APILogicError, format_error, validate_internal_call
from log import logger


class TextGeneratorFactory:
    PROVIDER_CLASS_MAP = {
        LLMProvider.azure.value: AzureTextGenerator,
        LLMProvider.vertex.value: VertexTextGenerator,
    }

    @validate_internal_call
    def __init__(self, ai_context: AIRequestContext, model_map: dict, provider_class_map: dict | None = None):
        self.provider = ai_context.provider.value
        self.shadow_mode = ai_context.shadow_mode
        self.model_map = model_map
        self._cache: dict[tuple, object] = {}

        # Allow override for tests
        self._provider_class_map = provider_class_map or self.PROVIDER_CLASS_MAP

        logger.info(f"PROVIDER: {self.provider}")
        logger.info(f"SHADOW MODE: {self.shadow_mode}")

    def get_generator(self, task: str):
        """
        Instantiate a text generator based on the chosen provider and request type (shadow/real).
        """
        # 1) Resolve model + cache key (same path for shadow vs real)
        model_name, cache_key = self._resolve_model_and_cache_key(task)

        # 2) Return from cache if present
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info(f"Using cached model for task '{task}' and provider '{self.provider}'")
            return cached

        # 3) Choose generator class
        generator_cls = self._choose_generator_class()

        # 4) Instantiate and cache
        generator = generator_cls(model_name)
        self._cache[cache_key] = generator
        return generator

    # --- Helpers ---

    def _resolve_model_and_cache_key(self, task: str) -> tuple[str, tuple]:
        """
        Returns (model_name, cache_key)
        """
        if self.shadow_mode:
            # Single mock model for all shadow tasks
            model_name = vr.MOCK_MODEL_NAME
            cache_key = (vr.MOCK_PROVIDER_NAME,)
            return model_name, cache_key

        provider_models = self.model_map.get(self.provider)
        if not provider_models:
            error_details = format_error(ErrorMessages.TextGeneration.NO_PROVIDER)
            raise APILogicError(error_details)

        model_name = provider_models.get(task) or provider_models.get("default")
        if not model_name:
            error_details = format_error(ErrorMessages.TextGeneration.NO_MODEL)
            raise APILogicError(error_details)

        # Log when falling back to default
        if task not in provider_models:
            logger.warning(
                "No model found for task %s and provider %s, using default model %s",
                task, self.provider, model_name
            )

        # Use structured tuple key (provider, model_name)
        cache_key = (self.provider, model_name)
        return model_name, cache_key

    def _choose_generator_class(self):
        if self.shadow_mode:
            return MockTextGenerator

        generator_cls = self._provider_class_map.get(self.provider)
        if not generator_cls:
            # Defensive: with Pydantic validation, likely never hit this.
            error_details = format_error(ErrorMessages.TextGeneration.NO_PROVIDER)
            raise APILogicError(error_details)
        return generator_cls